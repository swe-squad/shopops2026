import { useState } from 'react'
import { ChatClient } from './chat-client'
import { useBrowserNavigation } from './use-browser-navigation'
import { useMobileViewport } from './use-mobile-viewport'

function ChatSession({ token, onLock }: { token: string; onLock: () => void }) {
  const browser = useBrowserNavigation(token)
  return <main className="standalone-chat-content">
    <ChatClient token={token} onNavigate={browser.navigate} onLock={onLock} navigation={browser} />
  </main>
}

function App() {
  const [token, setToken] = useState('')
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
        <section className="unlock-card" aria-labelledby="unlock-title"><h2 id="unlock-title">Open your agent chat</h2><p>Use the same workspace token as your shop browser.</p>
          <form className="access-form" onSubmit={event => { event.preventDefault(); const value = draftToken.trim(); if (value) { setToken(value); setDraftToken('') } }}>
            <label htmlFor="workspace-token">Workspace access token</label><input id="workspace-token" type="password" autoComplete="off" spellCheck={false} required value={draftToken} onChange={event => setDraftToken(event.target.value)} aria-describedby="token-note" /><button className="primary-button" type="submit" disabled={!draftToken.trim()}>Unlock chat <span aria-hidden="true">→</span></button>
          </form><small id="token-note">Your token stays in this app until you lock or reload. Your shop browser has its own session.</small>
        </section>
        <p className="unlock-caption">A little clarity for your shop’s next step.</p>
      </main>
    </> : <ChatSession token={token} onLock={() => { setToken(''); setDraftToken('') }} />}
  </div>
}

export default App
