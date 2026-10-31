import { useEffect, useRef, useState } from 'react'
import { authHeaders, checkResponse } from './workspace-api'
import { ChatClient } from './chat-client'
import { useBrowserNavigation } from './use-browser-navigation'
import { useMobileViewport } from './use-mobile-viewport'

function ChatSession({ token, onLock, demo }: { token: string; onLock: () => void; demo: boolean }) {
  const browser = useBrowserNavigation(token, demo)
  const [reports, setReports] = useState(false)
  const [capabilityError, setCapabilityError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    void fetch('/api/chat/capabilities', { headers: authHeaders(token), signal: controller.signal }).then(async response => {
      await checkResponse(response, 'Could not load chat capabilities')
      const caps = await response.json()
      if (!controller.signal.aborted) setReports(caps.report_mode === true && caps.artifacts === true)
    }).catch(() => { if (!controller.signal.aborted) setCapabilityError('Report options are unavailable. Reload chat to try again.') })
    return () => controller.abort()
  }, [token])
  return <main className="standalone-chat-content">
    {capabilityError && <p role="status">{capabilityError}</p>}
    <ChatClient demo={demo} reports={reports} token={token} onNavigate={browser.navigate} onLock={onLock} navigation={browser} />
  </main>
}

function App() {
  const [token, setToken] = useState('')
  const [mode, setMode] = useState<'workspace_token' | 'demo_phone' | null>(null)
  const [error, setError] = useState('')
  const [signingIn, setSigningIn] = useState(false)
  const loginRequest = useRef<AbortController | null>(null)
  useEffect(() => () => loginRequest.current?.abort(), [])
  useEffect(() => {
    const controller = new AbortController()
    void fetch('/api/chat/auth/config', { signal: controller.signal }).then(async response => {
      await checkResponse(response, 'Could not load sign-in settings')
      const value = await response.json()
      if (!['workspace_token','demo_phone'].includes(value.mode)) throw new Error('Invalid sign-in settings.')
      if (!controller.signal.aborted) setMode(value.mode)
    }).catch(() => { if (!controller.signal.aborted) setError('Could not load sign-in settings. Reload to try again.') })
    return () => controller.abort()
  }, [])
  async function unlock() {
    const value = draftToken.trim()
    if (!value || signingIn || !mode) return
    if (mode === 'workspace_token') { setToken(value); setDraftToken(''); return }
    setSigningIn(true); setError('')
    const controller = new AbortController(); loginRequest.current = controller
    try {
      const response = await fetch('/api/chat/auth/demo-phone', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone_number: value }), signal: controller.signal })
      await checkResponse(response, 'Could not sign in to the demo')
      const session = await response.json()
      if (typeof session.access_token !== 'string' || !session.access_token) throw new Error('Invalid demo session.')
      if (!controller.signal.aborted) { setToken(session.access_token); setDraftToken('') }
    } catch { if (!controller.signal.aborted) setError('Demo sign-in failed. Check the configured demo number and try again.') }
    finally { if (!controller.signal.aborted) setSigningIn(false); loginRequest.current = null }
  }
  function lock() {
    const previous = token
    setToken(''); setDraftToken(''); setError('')
    if (mode === 'demo_phone') void fetch('/api/chat/auth/logout', { method: 'POST', headers: authHeaders(previous) }).then(response => { if (!response.ok) setError('Chat locked locally; server sign-out was unavailable.') }).catch(() => setError('Chat locked locally; server sign-out was unavailable.'))
  }
  const [draftToken, setDraftToken] = useState('')
  const shell = useMobileViewport()

  return <div className="app-shell standalone-chat" ref={shell}>
    {!token ? <>
      <header className="workspace-header">
        <a className="brand" href="/" aria-label="ShopOps chat"><img src="/brand/mark-primary.svg" className="brand-mark" alt="" /><span>shopops<span className="brand-period">.</span></span></a>
        <span className="chat-app-label">Agent chat</span>
      </header>
      <main className="chat-unlock">
        <div className="chat-welcome"><span className="eyebrow">YOUR ON-CALL COMPANION</span><h1>Your next move,<br />made clear.</h1><p>Talk through what needs attention in your shop, one message at a time.</p></div>
        <section className="unlock-card" aria-labelledby="unlock-title"><h2 id="unlock-title">Open your agent chat</h2><p>{mode === 'demo_phone' ? 'Demo phone sign-in. No OTP; phone ownership is not verified.' : 'Use the same workspace token as your shop browser.'}</p>
          <form className="access-form" onSubmit={event => { event.preventDefault(); void unlock() }}>
            <label htmlFor="workspace-token">{mode === 'demo_phone' ? 'Demo phone number' : 'Workspace access token'}</label><input id="workspace-token" type={mode === 'demo_phone' ? 'tel' : 'password'} autoComplete="off" spellCheck={false} required value={draftToken} onChange={event => setDraftToken(event.target.value)} aria-describedby="token-note" /><button className="primary-button" type="submit" disabled={!draftToken.trim() || !mode || signingIn}>Unlock chat <span aria-hidden="true">→</span></button>
          </form>{error && <p role="alert">{error}</p>}{!mode && !error && <p role="status">Loading sign-in settings…</p>}<small id="token-note">Your token stays in this app until you lock or reload. Your shop browser has its own session.</small>
        </section>
        <p className="unlock-caption">A little clarity for your shop’s next step.</p>
      </main>
    </> : <ChatSession token={token} demo={mode === 'demo_phone'} onLock={lock} />}
  </div>
}

export default App
