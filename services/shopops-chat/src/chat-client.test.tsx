import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatClient } from './chat-client'

const timestamp = '2026-10-31T09:00:00Z'
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })

function renderClient() {
  return render(<ChatClient token="workspace-secret" onNavigate={vi.fn()} onLock={vi.fn()} navigation={{ notice: '', failed: false, retry: vi.fn(), dismiss: vi.fn() }} />)
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('chat composer and recovery', () => {
  it('groups adjacent messages under actual day separators without repeating Today', async () => {
    const today = new Date().toISOString()
    const previousYear = new Date(new Date().getFullYear() - 1, 0, 2, 12).toISOString()
    vi.stubGlobal('fetch', vi.fn(async () => json([
      { id: 1, role: 'assistant', text: 'Previous conversation', created_at: previousYear },
      { id: 2, role: 'user', text: 'Current question', created_at: today },
      { id: 3, role: 'assistant', text: 'Current response', created_at: today },
    ])))
    renderClient()
    await screen.findByText('Current response')
    expect(screen.getAllByText('Today')).toHaveLength(1)
    expect(screen.getByRole('log', { name: 'Conversation' }).querySelectorAll('time')).toHaveLength(5)
  })

  it('keeps sending disabled until an explicit history retry succeeds', async () => {
    const history = [{ id: 4, role: 'assistant', text: 'Saved response', created_at: timestamp }]
    let available = false
    const fetchMock = vi.fn(async (_url: string, _options?: RequestInit) => json(available ? history : { detail: 'Unavailable' }, available ? 200 : 503))
    vi.stubGlobal('fetch', fetchMock)
    renderClient()
    await screen.findByRole('alert')
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
    const recovery = screen.getByRole('group', { name: 'Conversation recovery' })
    available = true
    fireEvent.click(within(recovery).getByRole('button', { name: 'Load conversation' }))
    await screen.findByText('Saved response')
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeEnabled()
    expect(screen.queryByRole('group', { name: 'Conversation recovery' })).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    for (const [url, options] of fetchMock.mock.calls) {
      expect(url).toBe('/api/chat/messages')
      expect(options?.method).toBeUndefined()
    }
  })

  it('does not send while composing text or inserting a new line', async () => {
    const fetchMock = vi.fn(async (_url: string, options?: RequestInit) => {
      if (options?.method !== 'POST') return json([])
      const message = { id: 5, role: 'assistant', text: 'Reply received', created_at: timestamp }
      return new Response(`data: ${JSON.stringify({ type: 'done', message })}\n\n`, { headers: { 'Content-Type': 'text/event-stream' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderClient()
    const composer = screen.getByRole('textbox', { name: 'Message' })
    await waitFor(() => expect(composer).toBeEnabled())
    fireEvent.change(composer, { target: { value: 'Kiểm tra đơn hàng' } })
    fireEvent.keyDown(composer, { key: 'Enter', isComposing: true })
    fireEvent.keyDown(composer, { key: 'Enter', shiftKey: true })
    expect(composer).toHaveValue('Kiểm tra đơn hàng')
    expect(fetchMock).toHaveBeenCalledOnce()
    fireEvent.keyDown(composer, { key: 'Enter' })
    await screen.findByText('Reply received')
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
    expect(composer).toHaveValue('')
    expect(composer).toHaveFocus()
  })
})
