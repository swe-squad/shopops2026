import { useEffect, useRef, useState } from 'react'
import { BrowserIcon } from './browser-icon'
import { authHeaders } from './workspace-api'

export function LoginPage({ onLogin }: { onLogin: (token: string) => void }) {
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])

  async function login() {
    const token = draft.trim()
    if (!token || request.current) return
    const controller = new AbortController()
    request.current = controller
    setPending(true)
    setError('')
    try {
      const response = await fetch('/api/operations/incidents', {
        headers: authHeaders(token), signal: controller.signal, cache: 'no-store',
      })
      if (controller.signal.aborted) return
      if (!response.ok) {
        setError(response.status === 401 ? 'Invalid workspace token. Please check it and try again.' : 'Could not connect to the workspace. Please try again.')
        return
      }
      setDraft('')
      onLogin(token)
    } catch {
      if (!controller.signal.aborted) setError('Could not connect to the workspace. Please try again.')
    } finally {
      if (!controller.signal.aborted) {
        request.current = null
        setPending(false)
      }
    }
  }

  return <section className="unlock-card login-card" aria-labelledby="login-title" lang="en">
    <span className="unlock-symbol"><BrowserIcon name="lock" /></span>
    <span className="eyebrow">YOUR WORKSPACE</span>
    <h1 id="login-title">Log in to ShopOps</h1>
    <p>A clearer view of your shop operations. Enter your token to continue.</p>
    <form className="access-form" onSubmit={event => { event.preventDefault(); void login() }} aria-busy={pending}>
      <label htmlFor="workspace-token">Workspace access token</label>
      <input id="workspace-token" type="password" autoComplete="off" spellCheck={false} required value={draft} disabled={pending} onChange={event => setDraft(event.target.value)} aria-describedby={error ? 'token-note login-error' : 'token-note'} />
      {error && <p id="login-error" className="login-error" role="alert">{error}</p>}
      <button className="primary-button" type="submit" disabled={!draft.trim() || pending}>{pending ? 'Checking…' : 'Log in'}<BrowserIcon name="arrow" /></button>
      {pending && <span className="sr-only" role="status">Checking your token</span>}
    </form>
    <small id="token-note">Your token stays in memory until you lock or reload this app. Log in to the chat app separately with the same token.</small>
  </section>
}
