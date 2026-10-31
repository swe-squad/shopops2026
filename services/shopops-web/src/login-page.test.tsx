import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './login-page'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
function submit(value = ' workspace-secret ') {
  fireEvent.change(screen.getByLabelText('Workspace access token'), { target: { value } })
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
}

describe('workspace login', () => {
  it('rejects blank input, validates a trimmed token and waits before creating a session', async () => {
    let resolve!: (response: Response) => void
    const fetchMock = vi.fn(() => new Promise<Response>(done => { resolve = done }))
    vi.stubGlobal('fetch', fetchMock)
    const onLogin = vi.fn()
    render(<LoginPage onLogin={onLogin} />)
    submit('   ')
    expect(fetchMock).not.toHaveBeenCalled()
    submit()
    expect(onLogin).not.toHaveBeenCalled()
    expect(screen.getByRole('button')).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith('/api/operations/incidents', expect.objectContaining({ headers: { Authorization: 'Bearer workspace-secret' }, cache: 'no-store', signal: expect.any(AbortSignal) }))
    await act(async () => resolve(new Response('[]')))
    expect(onLogin).toHaveBeenCalledExactlyOnceWith('workspace-secret')
    expect(screen.getByLabelText('Workspace access token')).toHaveValue('')
  })

  it.each([401, 500, 'network'])('keeps login available for retry after %s', async failure => {
    const fetchMock = vi.fn().mockImplementationOnce(() => failure === 'network' ? Promise.reject(new TypeError('Failed to fetch')) : Promise.resolve(new Response('', { status: failure as number }))).mockResolvedValue(new Response('[]'))
    vi.stubGlobal('fetch', fetchMock)
    const onLogin = vi.fn()
    render(<LoginPage onLogin={onLogin} />)
    submit()
    expect(await screen.findByRole('alert')).toHaveTextContent(failure === 401 ? 'Invalid workspace token' : 'Could not connect')
    expect(onLogin).not.toHaveBeenCalled()
    submit()
    await waitFor(() => expect(onLogin).toHaveBeenCalledOnce())
  })

  it('aborts on unmount and ignores a late successful response', async () => {
    let resolve!: (response: Response) => void
    const fetchMock = vi.fn((_url: string, _options: RequestInit) => new Promise<Response>(done => { resolve = done }))
    vi.stubGlobal('fetch', fetchMock)
    const onLogin = vi.fn()
    const view = render(<LoginPage onLogin={onLogin} />)
    submit()
    const signal = fetchMock.mock.calls[0][1].signal!
    view.unmount()
    expect(signal.aborted).toBe(true)
    await act(async () => resolve(new Response('[]')))
    expect(onLogin).not.toHaveBeenCalled()
  })
})
