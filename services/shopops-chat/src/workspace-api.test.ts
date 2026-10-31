import { describe, expect, it, vi } from 'vitest'
import { consumeEventStream } from './workspace-api'

const encoder = new TextEncoder()
const message = { id: 8, role: 'assistant', text: 'Xin chào 👋', created_at: '2026-10-31T09:00:00Z' }

function response(text: string, chunkSize = 1) {
  const bytes = encoder.encode(text)
  return new Response(new ReadableStream({
    start(controller) {
      for (let index = 0; index < bytes.length; index += chunkSize) controller.enqueue(bytes.slice(index, index + chunkSize))
      controller.close()
    },
  }), { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } })
}

describe('stream transport', () => {
  it('decodes fragmented UTF-8, CRLF boundaries, comments and multiline SSE data', async () => {
    const onEvent = vi.fn()
    await consumeEventStream(response(': keep-alive\r\n\r\ndata: {"type":"delta",\r\ndata: "text":"Xin chào 👋"}\r\n\r\ndata: ' + JSON.stringify({ type: 'done', message }) + '\r\n\r\n'), onEvent)
    expect(onEvent.mock.calls.map(([event]) => event)).toEqual([{ type: 'delta', text: message.text }, { type: 'done', message }])
  })

  it('rejects a truncated response instead of treating a partial answer as complete', async () => {
    await expect(consumeEventStream(response('data: {"type":"delta","text":"Partial"}\n\n'), vi.fn())).rejects.toThrow('interrupted')
  })

  it('reports provider errors after delivering earlier deltas', async () => {
    const onEvent = vi.fn()
    await expect(consumeEventStream(response('data: {"type":"delta","text":"Checking…"}\n\ndata: {"type":"error","message":"Agent unavailable. Try again later."}\n\n'), onEvent)).rejects.toThrow('Agent unavailable')
    expect(onEvent).toHaveBeenCalledOnce()
  })

  it.each(['null', '{"type":"done","message":{"text":"Missing fields"}}', 'invalid JSON'])('rejects an invalid event: %s', async value => {
    await expect(consumeEventStream(response(`data: ${value}\n\n`), vi.fn())).rejects.toThrow()
  })

  it('cancels a blocked stream read when stopped', async () => {
    const cancel = vi.fn()
    const controller = new AbortController()
    const body = new ReadableStream({ cancel })
    const consuming = consumeEventStream(new Response(body, { headers: { 'Content-Type': 'text/event-stream' } }), vi.fn(), controller.signal)
    controller.abort()
    await expect(consuming).rejects.toThrow()
    expect(cancel).toHaveBeenCalledOnce()
    expect(body.locked).toBe(false)
  })
})
