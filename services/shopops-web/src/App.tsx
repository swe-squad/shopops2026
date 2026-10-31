import { useState } from 'react'
import { BrowserPane } from './browser-pane'
import { useNavigationRequests } from './use-navigation-requests'

function BrowserSession({ token }: { token: string }) {
  const navigation = useNavigationRequests(token)
  return <main className="workspace-main standalone-browser">
    <div className="workspace-intro"><div><span className="eyebrow">THE DETAILS, IN VIEW</span><h1>Your shop, in view.</h1></div><p>Keep your chat app open.<br />Links from your agent appear here.</p></div>
    {navigation.error && <p className="navigation-warning" role="status">{navigation.error}</p>}
    <div className="standalone-browser-pane"><BrowserPane token={token} requestedUrl={navigation.request} /></div>
  </main>
}

function App() {
  const [token, setToken] = useState('')
  const [draftToken, setDraftToken] = useState('')

  return <div className="app-shell">
    <header className="workspace-header">
      <a className="brand" href="/" aria-label="ShopOps browser"><span className="brand-mark" aria-hidden="true">✳</span><span>shopops<span className="brand-period">.</span></span></a>
      <div className="workspace-heading"><span className="header-divider" aria-hidden="true" /><span>Shop browser</span></div>
      {token ? <button type="button" className="secondary-button lock-button" onClick={() => { setToken(''); setDraftToken('') }}>Lock workspace</button> : <span className="header-note">Your shop, in view.</span>}
    </header>
    {!token ? <main className="unlock-layout">
      <section className="welcome-copy"><span className="eyebrow">YOUR SHOP, ON TRACK</span><h1>A clearer view.<br />A better day for your shop.</h1><p>Review shop operations here. Keep your agent conversation in its own app, and open its links directly in this browser.</p><div className="welcome-panes" aria-hidden="true"><span>◫ &nbsp; Shop browser</span><span>↗</span><span>Your next move</span></div></section>
      <section className="unlock-card" aria-labelledby="unlock-title"><span className="unlock-symbol" aria-hidden="true">⌑</span><h2 id="unlock-title">Open your shop browser</h2><p>Enter your workspace access token to continue.</p>
        <form className="access-form" onSubmit={event => { event.preventDefault(); const value = draftToken.trim(); if (value) { setToken(value); setDraftToken('') } }}>
          <label htmlFor="workspace-token">Workspace access token</label><input id="workspace-token" type="password" autoComplete="off" spellCheck={false} required value={draftToken} onChange={event => setDraftToken(event.target.value)} aria-describedby="token-note" /><button className="primary-button" type="submit" disabled={!draftToken.trim()}>Unlock workspace <span aria-hidden="true">↗</span></button>
        </form><small id="token-note">Your token stays in this tab until you lock or reload. Unlock the chat app separately with the same workspace token.</small>
      </section>
    </main> : <BrowserSession token={token} />}
  </div>
}
export default App
