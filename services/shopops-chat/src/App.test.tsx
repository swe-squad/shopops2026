import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const timestamp = '2026-10-31T09:00:00Z'
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
const encoder = new TextEncoder()
const frame = (value: unknown) => encoder.encode(`data: ${JSON.stringify(value)}\n\n`)

async function unlock() {
  await waitFor(() => expect(screen.queryByText('Loading sign-in settings…')).not.toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('Workspace access token'), { target: { value: 'workspace-secret' } })
  fireEvent.click(screen.getByRole('button', { name: 'Unlock chat' }))
}

function setupStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>
  let requestSignal: AbortSignal | undefined
  let navigationFails = false
  const cancel = vi.fn()
  const stream = new ReadableStream<Uint8Array>({ start(value) { controller = value }, cancel })
  const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
    if (url === '/api/chat/auth/config') return json({ mode: 'workspace_token' })
    if (url === '/api/chat/capabilities') return json({report_mode:false,artifacts:false})
    if (url === '/api/operations/navigation') return json({ id: 5, url: '/shop/incidents' }, navigationFails ? 500 : 201)
    if (options?.method === 'POST') {
      requestSignal = options.signal as AbortSignal
      return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } })
    }
    return json([])
  })
  vi.stubGlobal('fetch', fetchMock)
  return { controller, fetchMock, cancel, getSignal: () => requestSignal, failNavigation: (value: boolean) => { navigationFails = value } }
}

async function send(text: string) {
  await waitFor(() => expect(screen.getByLabelText('Message')).toBeEnabled())
  fireEvent.change(screen.getByLabelText('Message'), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  await screen.findByRole('button', { name: 'Stop response' })
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('standalone Telegram-style chat', () => {
  it('loads only chat history and never embeds or displays the shop browser', async () => {
    const fetchMock = vi.fn(async (url: string) => url === '/api/chat/auth/config' ? json({mode:'workspace_token'}) : url === '/api/chat/capabilities' ? json({report_mode:false,artifacts:false}) : json([]))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await unlock()
    await screen.findByText('Keep your shop in view.')
    expect(fetchMock).toHaveBeenCalledWith('/api/chat/messages', expect.objectContaining({ headers: { Authorization: 'Bearer workspace-secret' } }))
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(screen.queryByRole('region', { name: 'Shop browser' })).not.toBeInTheDocument()
    expect(document.querySelector('iframe')).toBeNull()
  })

  it('renders fragmented streamed rich content and sends relative links through the navigation mailbox', async () => {
    const stream = setupStream()
    render(<App />)
    await unlock()
    await send('Review incidents')
    const text = 'Review [incidents](/shop/incidents).\n\n| Issue | Count |\n| --- | --- |\n| Late | 2 |\n\n`shipment_id`\n\n[Carrier](https://example.com/tracking)\n\n![remote](https://example.com/pixel.png)\n\n<script>alert(1)</script>'
    const bytes = frame({ type: 'delta', text })
    await act(async () => { stream.controller.enqueue(bytes.slice(0, 17)) })
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    await act(async () => { stream.controller.enqueue(bytes.slice(17)) })
    expect(await screen.findByRole('table')).toHaveTextContent('Late')
    expect(screen.getByText('shipment_id').tagName).toBe('CODE')
    expect(screen.getByRole('log').querySelector('script, img, iframe')).toBeNull()
    await act(async () => { stream.controller.enqueue(frame({ type: 'done', message: { id: 9, role: 'assistant', text, created_at: timestamp } })) })
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop response' })).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('link', { name: 'incidents' }))
    await screen.findByText('Link sent. Keep your shop browser open and unlocked to view it.')
    expect(stream.fetchMock).toHaveBeenCalledWith('/api/operations/navigation', expect.objectContaining({ method: 'POST', body: JSON.stringify({ url: '/shop/incidents' }) }))
    fireEvent.click(screen.getByRole('link', { name: 'Carrier' }))
    await waitFor(() => expect(stream.fetchMock).toHaveBeenCalledWith('/api/operations/navigation', expect.objectContaining({ body: JSON.stringify({ url: 'https://example.com/tracking' }) })))
    expect(screen.getByRole('log')).toHaveTextContent('Review incidents')
    expect(document.querySelector('iframe')).toBeNull()
  })

  it('retries failed link delivery explicitly without resending the chat turn', async () => {
    const stream = setupStream()
    stream.failNavigation(true)
    render(<App />)
    await unlock()
    await send('Open issues')
    const text = '[Incidents](/shop/incidents)'
    await act(async () => { stream.controller.enqueue(frame({ type: 'done', message: { id: 10, role: 'assistant', text, created_at: timestamp } })) })
    fireEvent.click(await screen.findByRole('link', { name: 'Incidents' }))
    await screen.findByText(/Could not open the link/)
    stream.failNavigation(false)
    fireEvent.click(screen.getByRole('button', { name: 'Retry opening link' }))
    await screen.findByText('Link sent. Keep your shop browser open and unlocked to view it.')
    expect(stream.fetchMock.mock.calls.filter(([url, options]) => url === '/api/chat/messages' && options?.method === 'POST')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss link notice' }))
    expect(screen.queryByRole('complementary', { name: 'Link delivery' })).not.toBeInTheDocument()
  })

  it('stops a response and requires a history reload without silently resending', async () => {
    const stream = setupStream()
    render(<App />)
    await unlock()
    await send('Look at shipping')
    await act(async () => { stream.controller.enqueue(frame({ type: 'delta', text: 'Checking shipments…' })) })
    fireEvent.click(screen.getByRole('button', { name: 'Stop response' }))
    await screen.findByText('Response stopped. Load the conversation before sending again.')
    expect(stream.getSignal()?.aborted).toBe(true)
    expect(stream.cancel).toHaveBeenCalled()
    expect(screen.getByLabelText('Message')).toBeDisabled()
    expect(screen.getByText('Checking shipments…')).toBeInTheDocument()
    fireEvent.click(within(screen.getByRole('group', { name: 'Conversation recovery' })).getByRole('button', { name: 'Load conversation' }))
    await waitFor(() => expect(screen.getByLabelText('Message')).toBeEnabled())
    expect(stream.fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
  })

  it('follows streaming at the bottom, leaves readers in place, and resumes on request', async () => {
    const stream = setupStream()
    render(<App />)
    await unlock()
    await send('Review shipments')
    const conversation = screen.getByRole('log', { name: 'Conversation' })
    let height = 1000
    let top = 700
    Object.defineProperties(conversation, {
      scrollHeight: { configurable: true, get: () => height },
      clientHeight: { configurable: true, value: 300 },
      scrollTop: { configurable: true, get: () => top, set: value => { top = Math.max(0, Math.min(value, height - 300)) } },
    })
    fireEvent.scroll(conversation)
    height = 1200
    await act(async () => { stream.controller.enqueue(frame({ type: 'delta', text: 'First update. ' })) })
    expect(conversation.scrollTop).toBe(900)

    conversation.scrollTop = 240
    fireEvent.scroll(conversation)
    expect(screen.getByRole('button', { name: 'Jump to latest' })).toBeInTheDocument()
    height = 1400
    await act(async () => { stream.controller.enqueue(frame({ type: 'delta', text: 'More evidence arrived.' })) })
    expect(conversation.scrollTop).toBe(240)
    fireEvent.click(screen.getByRole('button', { name: 'New reply · Jump to latest' }))
    expect(conversation.scrollTop).toBe(1100)
    expect(conversation).toHaveFocus()
    expect(screen.queryByRole('button', { name: /Jump to latest/ })).not.toBeInTheDocument()

    height = 1500
    await act(async () => { stream.controller.enqueue(frame({ type: 'delta', text: ' Final detail.' })) })
    expect(conversation.scrollTop).toBe(1200)
    fireEvent.click(screen.getByRole('button', { name: 'Stop response' }))
    await screen.findByText('Response stopped. Load the conversation before sending again.')
  })

  it('keeps a queued draft while rejecting duplicate submissions during streaming', async () => {
    const stream = setupStream()
    render(<App />)
    await unlock()
    await send('First question')
    const composer = screen.getByRole('textbox', { name: 'Message' })
    fireEvent.change(composer, { target: { value: 'My follow-up' } })
    fireEvent.keyDown(composer, { key: 'Enter' })
    fireEvent.keyDown(composer, { key: 'Enter' })
    expect(composer).toHaveValue('My follow-up')
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
    expect(stream.fetchMock.mock.calls.filter(([url, options]) => url === '/api/chat/messages' && options?.method === 'POST')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Stop response' }))
    await screen.findByText('Response stopped. Load the conversation before sending again.')
  })

  it('aborts in-flight streaming and clears its own token when locked', async () => {
    const stream = setupStream()
    render(<App />)
    await unlock()
    await send('Check my shop')
    fireEvent.click(screen.getByRole('button', { name: 'Chat menu' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Lock' }))
    expect(screen.getByRole('heading', { name: 'Open your agent chat' })).toBeInTheDocument()
    expect(stream.getSignal()?.aborted).toBe(true)
    expect(screen.getByLabelText('Workspace access token')).toHaveValue('')
    expect(screen.queryByText('Check my shop')).not.toBeInTheDocument()
  })
})

it('uses the single demo phone flow, capabilities and server logout without OTP', async () => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url === '/api/chat/auth/config') return json({mode:'demo_phone'})
    if (url === '/api/chat/auth/demo-phone') {
      expect(JSON.parse(options?.body as string)).toEqual({phone_number:'+84900000001'})
      return json({access_token:'opaque-session',expires_at:'2026-10-31T17:00:00Z'})
    }
    if (url === '/api/chat/capabilities') return json({report_mode:true,artifacts:true})
    if (url === '/api/chat/auth/logout') return new Response(null,{status:204})
    return json([])
  })
  vi.stubGlobal('fetch',fetcher)
  render(<App />)
  const phone = await screen.findByLabelText('Demo phone number')
  expect(screen.getByText(/No OTP/)).toBeInTheDocument()
  fireEvent.change(phone,{target:{value:'+84900000001'}})
  fireEvent.click(screen.getByRole('button',{name:'Unlock chat'}))
  await screen.findByRole('combobox',{name:'Response format'})
  expect(screen.queryByLabelText('Demo phone number')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'Chat menu'}))
  fireEvent.click(screen.getByRole('menuitem',{name:'Lock'}))
  expect(await screen.findByLabelText('Demo phone number')).toHaveValue('')
  expect(fetcher).toHaveBeenCalledWith('/api/chat/auth/logout',expect.objectContaining({headers:{Authorization:'Bearer opaque-session'}}))
  expect(localStorage.length).toBe(0)
})
