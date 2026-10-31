import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const json = (value: unknown) => new Response(JSON.stringify(value))
beforeEach(() => {
  window.history.replaceState(null, '', '/')
  vi.stubGlobal('fetch', vi.fn(async (url: string) => json(url.endsWith('/navigation') ? null : url.startsWith('/api/mock/') ? { connections: [] } : [])))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/') })

async function login() {
  fireEvent.change(await screen.findByLabelText('Workspace access token'), { target: { value: 'route-test-token' } })
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
  await screen.findByLabelText('Browser address')
}

describe('public and protected routes', () => {
  it('keeps landing public, logs in to Connections and preserves an in-memory session through home', async () => {
    render(<App />)
    expect(screen.queryByLabelText('Workspace access token')).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
    fireEvent.click(screen.getAllByRole('link', { name: 'Log in' })[0])
    expect(window.location.pathname).toBe('/login')
    await login()
    expect(window.location.pathname).toBe('/shop/connections')
    fireEvent.click(screen.getByRole('link', { name: 'ShopOps browser' }))
    expect(window.location.pathname).toBe('/')
    fireEvent.click(screen.getAllByRole('link', { name: 'Open workspace' })[0])
    expect(await screen.findByLabelText('Browser address')).toHaveValue(`${window.location.origin}/shop/connections`)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    expect(window.location.href).not.toContain('route-test-token')
  })

  it('returns to a deep link and requires login again after a document remount', async () => {
    window.history.replaceState(null, '', '/shop/incidents?filter=open#incident-7')
    const view = render(<App />)
    await login()
    expect(screen.getByLabelText('Browser address')).toHaveValue(`${window.location.origin}/shop/incidents?filter=open#incident-7`)
    view.unmount()
    render(<App />)
    await screen.findByLabelText('Workspace access token')
    expect(screen.queryByLabelText('Browser address')).not.toBeInTheDocument()
    expect(new URLSearchParams(window.location.search).get('next')).toBe('/shop/incidents?filter=open#incident-7')
  })

  it('falls back from unsafe next and guards Back after locking', async () => {
    window.history.replaceState(null, '', '/login?next=https://evil.test/shop/incidents')
    render(<App />)
    await login()
    expect(window.location.pathname).toBe('/shop/connections')
    fireEvent.click(screen.getByRole('button', { name: 'Lock workspace' }))
    await screen.findByLabelText('Workspace access token')
    act(() => {
      window.history.pushState(null, '', '/shop/incidents')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(screen.queryByLabelText('Browser address')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Workspace access token')).toHaveValue('')
  })

  it('redirects an already authenticated login visit and shows a real unknown-page state', async () => {
    window.history.replaceState(null, '', '/login')
    render(<App />)
    await login()
    act(() => {
      window.history.pushState(null, '', '/login?next=%2Fshop%2Foverview')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    await waitFor(() => expect(window.location.pathname).toBe('/shop/overview'))
    act(() => {
      window.history.pushState(null, '', '/unknown')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Browser address')).not.toBeInTheDocument()
  })
})
