export type Artifact = { id: string; filename: string; media_type: 'text/markdown' | 'application/json'; size: number; sha256: string; availability: 'available' | 'expired' | 'unavailable' }
export type Message = { id: number | string; role: 'user' | 'assistant'; text: string; created_at: string; kind?: 'answer' | 'clarification' | 'cannot_answer' | null; sources?: { type: 'data' | 'knowledge' | 'history'; reference: string }[] | null; artifacts?: Artifact[] | null }

export function validMessage(value: unknown): value is Message {
  if (!value || typeof value !== 'object') return false
  const m = value as Message
  if (!(typeof m.id === 'string' || typeof m.id === 'number') || !['user','assistant'].includes(m.role) || typeof m.text !== 'string' || typeof m.created_at !== 'string') return false
  if (m.kind != null && !['answer','clarification','cannot_answer'].includes(m.kind)) return false
  if (m.sources != null && (!Array.isArray(m.sources) || !m.sources.every(s => s && ['data','knowledge','history'].includes(s.type) && typeof s.reference === 'string' && s.reference.length > 0))) return false
  if (m.artifacts != null && (!Array.isArray(m.artifacts) || m.artifacts.length > 2 || !m.artifacts.every(a => a && typeof a.id === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(a.id) && typeof a.filename === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(a.filename) && !a.filename.includes('..') && ['text/markdown','application/json'].includes(a.media_type) && Number.isInteger(a.size) && a.size >= 0 && a.size <= 1048576 && /^[a-f0-9]{64}$/.test(a.sha256) && ['available','expired','unavailable'].includes(a.availability)))) return false
  return true
}
export type StreamEvent = { type: 'delta'; text: string } | { type: 'done'; message: Message } | { type: 'error'; message: string }

export function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

export async function checkResponse(response: Response, action: string) {
  if (response.ok) return
  if (response.status === 401) throw new Error('Your session is not valid. Lock the chat and sign in again.')
  if (response.status === 503) throw new Error(`${action}. The service is unavailable. Please try again.`)
  throw new Error(`${action} (${response.status}). Please try again.`)
}

export async function loadMessages(token: string, signal: AbortSignal): Promise<Message[]> {
  const response = await fetch('/api/chat/messages', { headers: authHeaders(token), signal })
  await checkResponse(response, 'Could not load the conversation')
  const messages: unknown = await response.json()
  if (!Array.isArray(messages) || !messages.every(validMessage)) throw new Error('The conversation returned invalid messages.')
  return messages
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
    else if (event.type === 'done' && validMessage(event.message) && event.message.role === 'assistant') {
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

export async function streamMessage(token: string, text: string, signal: AbortSignal, onEvent: (event: StreamEvent) => void, outputMode: 'text' | 'report' = 'text', clientMessageId: string = crypto.randomUUID()) {
  const response = await fetch('/api/chat/messages', {
    method: 'POST', headers: { ...authHeaders(token), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ text, output_mode: outputMode, client_message_id: clientMessageId }), signal,
  })
  await checkResponse(response, 'Could not send the message')
  await consumeEventStream(response, onEvent, signal)
}

export async function downloadArtifact(token: string, artifact: Artifact, signal: AbortSignal) {
  const response = await fetch(`/api/chat/artifacts/${encodeURIComponent(artifact.id)}/content`, { headers: authHeaders(token), signal, redirect: 'error' })
  if (response.status === 410) throw new Error('This report is no longer available.')
  await checkResponse(response, 'Could not download the report')
  if (response.headers.get('content-type')?.split(';')[0] !== artifact.media_type || !response.body) throw new Error('Invalid report content.')
  const reader = response.body.getReader()
  const chunks: Uint8Array<ArrayBuffer>[] = []
  let size = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      signal.throwIfAborted()
      if (done) break
      size += value.byteLength
      if (size > artifact.size || size > 1048576) throw new Error('Report exceeds the supported size.')
      chunks.push(new Uint8Array(value))
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock() }
  if (size !== artifact.size) throw new Error('Incomplete report download.')
  const blob = new Blob(chunks, { type: artifact.media_type })
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()))).map(b => b.toString(16).padStart(2,'0')).join('')
  if (hash !== artifact.sha256) throw new Error('Invalid report content.')
  const url = URL.createObjectURL(blob)
  try { const link = document.createElement('a'); link.href = url; link.download = artifact.filename; link.click() }
  finally { URL.revokeObjectURL(url) }
}
