import { useState } from 'react'
import { ChatClient } from './chat-client'
import { useBrowserNavigation } from './use-browser-navigation'

function ChatSession({ token }: { token: string }) {
  const browser = useBrowserNavigation(token)
  return <main className="standalone-chat-content">
    <ChatClient token={token} onNavigate={browser.navigate} />
    {browser.notice && <div className={`navigation-notice ${browser.failed ? 'navigation-failed' : ''}`} role={browser.failed ? 'alert' : 'status'}><p>{browser.notice}</p>{browser.failed && <button className="text-button" onClick={browser.retry}>Retry opening link</button>}</div>}
  </main>
}

function App() {
  const [token, setToken] = useState('')
  const [draftToken, setDraftToken] = useState('')

  return <div className="app-shell standalone-chat">
    <header className="workspace-header">
      <a className="brand" href="/" aria-label="ShopOps chat"><span className="brand-mark" aria-hidden="true">✳</span><span>shopops<span className="brand-period">.</span></span></a>
      <span className="chat-app-label">Agent chat</span>
      {token && <button type="button" className="secondary-button lock-button" onClick={() => { setToken(''); setDraftToken('') }}>Lock</button>}
    </header>
    {!token ? <main className="chat-unlock">
      <div className="chat-welcome"><span className="eyebrow">YOUR ON-CALL COMPANION</span><h1>Your agent,<br />a message away.</h1><p>Talk through the next step for your shop. Open links in your separate shop browser.</p></div>
      <section className="unlock-card" aria-labelledby="unlock-title"><h2 id="unlock-title">Open your agent chat</h2><p>Use the same workspace token as your shop browser.</p>
        <form className="access-form" onSubmit={event => { event.preventDefault(); const value = draftToken.trim(); if (value) { setToken(value); setDraftToken('') } }}>
          <label htmlFor="workspace-token">Workspace access token</label><input id="workspace-token" type="password" autoComplete="off" spellCheck={false} required value={draftToken} onChange={event => setDraftToken(event.target.value)} aria-describedby="token-note" /><button className="primary-button" type="submit" disabled={!draftToken.trim()}>Unlock chat <span aria-hidden="true">↗</span></button>
        </form><small id="token-note">Your token stays in this app until you lock or reload. Your shop browser has its own session.</small>
      </section>
    </main> : <ChatSession token={token} />}
  </div>
}

export default App
