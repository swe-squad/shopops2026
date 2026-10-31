import { expect, it, vi, afterEach } from 'vitest'
import { consumeEventStream, loadMessages, streamMessage } from './workspace-api'

afterEach(() => vi.unstubAllGlobals())
it('rejects malformed optional metadata in canonical history', async () => {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify([{id:'uuid',role:'assistant',text:'Hello',created_at:'2026-10-31',artifacts:[{id:'../evil'}]}]))))
  await expect(loadMessages('token',new AbortController().signal)).rejects.toThrow()
})
it('rejects malformed optional metadata in done', async () => {
  const payload='data: '+JSON.stringify({type:'done',message:{id:'uuid',role:'assistant',text:'x',created_at:'2026-10-31',kind:'invented'}})+'\n\n'
  await expect(consumeEventStream(new Response(payload,{headers:{'Content-Type':'text/event-stream'}}),()=>{})).rejects.toThrow()
})
it('sends a durable client ID and selected output mode', async () => {
  const fetcher=vi.fn().mockResolvedValue(new Response('data: {"type":"done","message":{"id":"uuid","role":"assistant","text":"OK","created_at":"2026-10-31"}}\n\n',{headers:{'Content-Type':'text/event-stream'}}))
  vi.stubGlobal('fetch',fetcher)
  await streamMessage('token','Hello',new AbortController().signal,()=>{},'report','stable-id')
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({text:'Hello',output_mode:'report',client_message_id:'stable-id'})
})
