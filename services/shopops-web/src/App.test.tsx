import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })

function unlock() {
  fireEvent.change(screen.getByLabelText('Workspace access token'), { target: { value: 'workspace-secret' } })
  fireEvent.click(screen.getByRole('button', { name: /unlock workspace/i }))
}

beforeEach(() => window.history.replaceState(null, '', '/shop/overview'))
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/') })

describe('standalone shop browser', () => {
  it('starts the demo after unlock and reads server state again across tabs and lock/unlock', async () => {
    window.history.replaceState(null, '', '/')
    let connected = false
    vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
      if (url.endsWith('/navigation')) return json(null)
      if (!url.startsWith('/api/mock/')) return json([])
      if (options?.method === 'PUT') { connected = true; return json({ platform: 'shopee', connected, mock: true }) }
      return json({ connections: [{ platform: 'shopee', connected, mock: true }, { platform: 'tiktok', connected: false, mock: true }] })
    }))
    render(<App />)
    unlock()
    expect(screen.getByLabelText('Browser address')).toHaveValue(`${window.location.origin}/shop/connections`)
    await screen.findAllByText('Not connected')
    fireEvent.click(screen.getByRole('button', { name: 'Log in to Shopee' }))
    await screen.findByRole('heading', { name: 'Connection successful' })
    fireEvent.click(screen.getByRole('button', { name: 'New browser tab' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), { target: { value: 'Keep my draft' } })
    fireEvent.click(screen.getByRole('link', { name: 'Connections' }))
    const panel = within(screen.getByRole('tabpanel'))
    await panel.findByRole('button', { name: 'View Shopee connection' })
    expect(panel.getByRole('button', { name: 'Log in to TikTok' })).toBeEnabled()
    fireEvent.click(screen.getByRole('link', { name: 'Overview' }))
    expect(screen.getByRole('textbox', { name: 'Title' })).toHaveValue('Keep my draft')
    fireEvent.click(screen.getByRole('tab', { name: 'Connections — tab 1' }))
    await screen.findByRole('heading', { name: 'Connection successful' })
    expect(screen.getByRole('tab', { name: 'Connections — tab 1' })).not.toHaveAttribute('tabindex', '-1')
    fireEvent.click(screen.getByRole('button', { name: 'Lock workspace' }))
    unlock()
    await screen.findByRole('button', { name: 'View Shopee connection' })
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('loads and saves operations without loading or displaying the chat app', async () => {
    const incident = { id: 7, title: 'Late shipment', detail: 'Review the carrier handoff.', created_at: '2026-10-31T09:00:00Z' }
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
      if (url.endsWith('/navigation')) return json(null)
      return options?.method === 'POST' ? json(incident) : json([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    unlock()
    await screen.findByText('No incidents yet')
    expect(screen.queryByRole('region', { name: 'Agent chat' })).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/operations/incidents', expect.objectContaining({ headers: { Authorization: 'Bearer workspace-secret' } }))
    expect(fetchMock.mock.calls.some(([url]) => url.includes('/chat/'))).toBe(false)
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: incident.title } })
    fireEvent.change(screen.getByLabelText(/Details/), { target: { value: incident.detail } })
    fireEvent.click(screen.getByRole('button', { name: 'Add incident' }))
    await screen.findByRole('heading', { name: incident.title })
    expect(fetchMock).toHaveBeenCalledWith('/api/operations/incidents', expect.objectContaining({ method: 'POST', body: JSON.stringify({ title: incident.title, detail: incident.detail }) }))
    expect(window.localStorage.getItem('token')).toBeNull()
    expect(window.sessionStorage.getItem('token')).toBeNull()
  })

  it('receives new link events, resolves shop paths on its own origin, and deduplicates old events', async () => {
    let navigation = { id: 7, url: '/shop/incidents' }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => json(url.endsWith('/navigation') ? navigation : [])))
    render(<App />)
    unlock()
    await waitFor(() => expect(screen.getByLabelText('Browser address')).toHaveValue(`${window.location.origin}/shop/incidents`))
    fireEvent.click(screen.getByRole('link', { name: 'Overview' }))
    expect(screen.getByLabelText('Browser address')).toHaveValue(`${window.location.origin}/shop/overview`)
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 1050)) })
    expect(screen.getByLabelText('Browser address')).toHaveValue(`${window.location.origin}/shop/overview`)
    navigation = { id: 8, url: 'https://example.com/tracking' }
    const iframe = await screen.findByTitle('Website: example.com', {}, { timeout: 2200 })
    expect(iframe).toHaveAttribute('sandbox', 'allow-scripts allow-forms')
    expect(iframe).toHaveAttribute('referrerpolicy', 'no-referrer')
    expect(iframe.outerHTML).not.toContain('workspace-secret')
    expect(screen.getByRole('link', { name: /Open in new tab/ })).toHaveAttribute('rel', 'noopener noreferrer')
    fireEvent.click(screen.getByRole('button', { name: 'Go back' }))
    expect(screen.getByLabelText('Browser address')).toHaveValue(`${window.location.origin}/shop/overview`)
    fireEvent.click(screen.getByRole('button', { name: 'Go forward' }))
    await screen.findByTitle('Website: example.com')
  })

  it('reports invalid addresses and operations errors without executing unsafe URLs', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/navigation') ? json(null) : new Response('', { status: 500 })))
    render(<App />)
    unlock()
    await screen.findByText(/Could not load incidents/)
    fireEvent.change(screen.getByLabelText('Browser address'), { target: { value: 'javascript:alert(1)' } })
    fireEvent.click(screen.getByRole('button', { name: 'Open address' }))
    expect(screen.getByText('Enter an http or https URL, or a local shop path.')).toHaveAttribute('role', 'alert')
    expect(document.querySelector('iframe')).toBeNull()
  })

  it('aborts navigation polling and operation requests when locking', async () => {
    const fetchMock = vi.fn(async (url: string, _options?: RequestInit) => json(url.endsWith('/navigation') ? null : []))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    unlock()
    await screen.findByText('No incidents yet')
    const signals = fetchMock.mock.calls.map(call => call[1]?.signal as AbortSignal)
    fireEvent.click(screen.getByRole('button', { name: 'Lock workspace' }))
    expect(screen.getByRole('heading', { name: 'Open your shop browser' })).toBeInTheDocument()
    expect(signals.every(signal => signal.aborted)).toBe(true)
    expect(screen.getByLabelText('Workspace access token')).toHaveValue('')
  })
})
