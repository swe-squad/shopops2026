import { useState } from 'react'
import { BrowserPane } from './browser-pane'
import { BrowserIcon } from './browser-icon'
import { useNavigationRequests } from './use-navigation-requests'

function BrowserSession({ token }: { token: string }) {
  const navigation = useNavigationRequests(token)
  return <main className="workspace-main standalone-browser">
    {navigation.error && <p className="navigation-warning" role="status">{navigation.error}</p>}
    <BrowserPane token={token} requestedUrl={navigation.request} />
  </main>
}

function App() {
  const [token, setToken] = useState('')
  const [draftToken, setDraftToken] = useState('')

  return <div className="app-shell">
    <header className="workspace-header">
      <a className="brand" href="/" aria-label="ShopOps browser"><img className="brand-mark" src="/brand/mark-primary.svg" alt="" width="24" height="24" /><span>shopops<span className="brand-period">.</span></span></a>
      <div className="workspace-heading"><span className="header-divider" aria-hidden="true" /><span>Seller workspace</span></div>
      {token ? <button type="button" className="secondary-button lock-button" onClick={() => { setToken(''); setDraftToken('') }}><BrowserIcon name="lock" />Lock workspace</button> : <span className="header-note">Your next move, made clear.</span>}
    </header>
    {!token ? <main className="unlock-scroll"><div className="unlock-layout">
      <section className="welcome-copy"><span className="eyebrow">CLARITY IN THE CHAOS</span><h1>Know what matters.<br />See what’s next.</h1><p>Keep your shop operations in view. Review issues, capture the details, and follow links from your ShopOps agent.</p><div className="welcome-panes"><BrowserIcon name="list" /><span>Your shop. A clearer perspective.</span></div></section>
      <section className="unlock-card" aria-labelledby="unlock-title"><span className="unlock-symbol"><BrowserIcon name="lock" /></span><h2 id="unlock-title">Open your shop browser</h2><p>Enter your workspace access token to continue.</p>
        <form className="access-form" onSubmit={event => { event.preventDefault(); const value = draftToken.trim(); if (value) { setToken(value); setDraftToken('') } }}>
          <label htmlFor="workspace-token">Workspace access token</label><input id="workspace-token" type="password" autoComplete="off" spellCheck={false} required value={draftToken} onChange={event => setDraftToken(event.target.value)} aria-describedby="token-note" /><button className="primary-button" type="submit" disabled={!draftToken.trim()}>Unlock workspace <BrowserIcon name="arrow" /></button>
        </form><small id="token-note">Your token stays in memory until you lock or reload this app. Unlock the chat app separately with the same workspace token.</small>
      </section>
    </div></main> : <BrowserSession token={token} />}
  </div>
}
export default App
