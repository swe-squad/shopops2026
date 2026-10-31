import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const config = { browser_url: 'https://browser.example.com', chat_url: 'https://chat.example.com' }
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('independent app viewer', () => {
  it('loads only public config and mounts separate trusted client documents', async () => {
    const fetchMock = vi.fn(async () => json(config))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const browser = await screen.findByTitle('Shop browser app')
    const chat = screen.getByTitle('Agent chat app')
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith('/client-config.json', expect.objectContaining({ credentials: 'omit', cache: 'no-store', headers: { Accept: 'application/json' } }))
    expect(browser).toHaveAttribute('src', config.browser_url)
    expect(chat).toHaveAttribute('src', config.chat_url)
    for (const frame of [browser, chat]) {
      expect(frame).toHaveAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox')
      expect(frame).toHaveAttribute('referrerpolicy', 'no-referrer')
      expect(frame.getAttribute('sandbox')).not.toContain('top-navigation')
    }
    expect(screen.queryByLabelText('Workspace access token')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Message')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open browser app in new tab' })).toHaveAttribute('href', config.browser_url)
    expect(screen.getByRole('link', { name: 'Open chat app in new tab' })).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('reloads one client without remounting or changing the other client', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(config)))
    render(<App />)
    const browserBefore = await screen.findByTitle('Shop browser app')
    const chatBefore = screen.getByTitle('Agent chat app')
    fireEvent.click(screen.getByRole('button', { name: 'Reload browser app' }))
    const browserAfter = screen.getByTitle('Shop browser app')
    expect(browserAfter).not.toBe(browserBefore)
    expect(screen.getByTitle('Agent chat app')).toBe(chatBefore)
    expect(browserBefore.isConnected).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Reload chat app' }))
    expect(screen.getByTitle('Agent chat app')).not.toBe(chatBefore)
    expect(screen.getByTitle('Shop browser app')).toBe(browserAfter)
  })

  it('switches narrow views without replacing either document or refetching config', async () => {
    const fetchMock = vi.fn(async () => json(config))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const browser = await screen.findByTitle('Shop browser app')
    const chat = screen.getByTitle('Agent chat app')
    fireEvent.click(screen.getByRole('button', { name: 'Chat' }))
    expect(screen.getByRole('button', { name: 'Chat' })).toHaveAttribute('aria-pressed', 'true')
    expect(chat.parentElement?.closest('[data-active-client]')).toHaveAttribute('data-active-client', 'chat')
    fireEvent.click(screen.getByRole('button', { name: 'Browser' }))
    expect(screen.getByRole('button', { name: 'Browser' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTitle('Shop browser app')).toBe(browser)
    expect(screen.getByTitle('Agent chat app')).toBe(chat)
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('keeps invalid config out of frames and retries only the config request', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json({ browser_url: 'https://same.example.com', chat_url: 'https://same.example.com' })).mockResolvedValueOnce(json(config))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('separate origins')
    expect(document.querySelector('iframe')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Retry loading apps' }))
    await screen.findByTitle('Shop browser app')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('shows a useful retry state when configuration cannot be fetched', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 503 })))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the client app configuration')
    expect(document.querySelector('iframe')).toBeNull()
    expect(screen.getByRole('button', { name: 'Retry loading apps' })).toBeEnabled()
  })

  it('aborts a pending config read and ignores stale completion after unmount', async () => {
    let resolve!: (value: Response) => void
    const fetchMock = vi.fn((_url: string, _options?: RequestInit) => new Promise<Response>(value => { resolve = value }))
    vi.stubGlobal('fetch', fetchMock)
    const app = render(<App />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    const signal = fetchMock.mock.calls[0][1]?.signal as AbortSignal
    app.unmount()
    expect(signal.aborted).toBe(true)
    await act(async () => { resolve(json(config)) })
    expect(document.querySelector('iframe')).toBeNull()
  })
})

