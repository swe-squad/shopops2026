export type Message = { id: number | string; role: 'user' | 'assistant'; text: string; created_at: string }
export type StreamEvent = { type: 'delta'; text: string } | { type: 'done'; message: Message } | { type: 'error'; message: string }

export function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

export async function checkResponse(response: Response, action: string) {
  if (response.ok) return
  if (response.status === 401) throw new Error('Workspace token is not valid. Lock the workspace and try again.')
  if (response.status === 503) throw new Error(`${action}. The service is unavailable. Please try again.`)
  throw new Error(`${action} (${response.status}). Please try again.`)
}

export async function loadMessages(token: string, signal: AbortSignal): Promise<Message[]> {
  const response = await fetch('/api/chat/messages', { headers: authHeaders(token), signal })
  await checkResponse(response, 'Could not load the conversation')
  return response.json() as Promise<Message[]>
}

// Event boundaries and UTF-8 characters can span arbitrary network chunks.
export async function consumeEventStream(response: Response, onEvent: (event: StreamEvent) => void, signal?: AbortSignal) {
  signal?.throwIfAborted()
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('The orchestrator did not return a streaming response.')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let receivedSize = 0
  let complete = false
  const cancelRead = () => { void reader.cancel().catch(() => {}) }
  signal?.addEventListener('abort', cancelRead, { once: true })

  function dispatch(frame: string) {
    const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).replace(/^ /, '')).join('\n')
    if (!data) return
    let event: StreamEvent
    try { event = JSON.parse(data) as StreamEvent } catch { throw new Error('The orchestrator returned an invalid event.') }
    if (event.type === 'delta' && typeof event.text === 'string') onEvent(event)
    else if (event.type === 'done' && event.message && event.message.role === 'assistant' && typeof event.message.text === 'string'
      && (typeof event.message.id === 'string' || typeof event.message.id === 'number') && typeof event.message.created_at === 'string') {
      complete = true
      onEvent(event)
    } else if (event.type === 'error' && typeof event.message === 'string') throw new Error(event.message)
    else throw new Error('The orchestrator returned an invalid event.')
  }
  try {
    while (!complete) {
      const { value, done } = await reader.read()
      signal?.throwIfAborted()
      const chunk = done ? decoder.decode() : decoder.decode(value, { stream: true })
      receivedSize += chunk.length
      if (receivedSize > 1_000_000) throw new Error('The response exceeded the supported message size.')
      buffer += chunk
      let boundary: RegExpExecArray | null
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        dispatch(buffer.slice(0, boundary.index))
        buffer = buffer.slice(boundary.index + boundary[0].length)
        if (complete) break
      }
      if (done) {
        if (buffer.trim() && !complete) dispatch(buffer)
        break
      }
    }
    if (!complete) throw new Error('The response was interrupted. Load the conversation before sending again.')
  } finally {
    signal?.removeEventListener('abort', cancelRead)
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

export async function streamMessage(token: string, text: string, signal: AbortSignal, onEvent: (event: StreamEvent) => void) {
  const response = await fetch('/api/chat/messages', {
    method: 'POST', headers: { ...authHeaders(token), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ text }), signal,
  })
  await checkResponse(response, 'Could not send the message')
  await consumeEventStream(response, onEvent, signal)
}
