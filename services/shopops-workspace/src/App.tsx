import { useState } from 'react'
import { ClientFrame } from './client-frame'
import { useClientConfig } from './use-client-config'

function App() {
  const clients = useClientConfig()
  const [activeClient, setActiveClient] = useState<'browser' | 'chat'>('browser')

  return <div className="viewer">
    <header className="viewer-header">
      <a className="brand" href="/" aria-label="ShopOps workspace">
        <img src="/brand/mark-primary.svg" width="24" height="24" alt="" />
        <span>shopops<span className="brand-period">.</span></span>
      </a>
      <span className="header-divider" aria-hidden="true" />
      <h1>Workspace</h1>
      {clients.config && <div className="view-switch" role="group" aria-label="Visible app">
        <button type="button" aria-pressed={activeClient === 'browser'} aria-controls="browser-client" onClick={() => setActiveClient('browser')}>Browser</button>
        <button type="button" aria-pressed={activeClient === 'chat'} aria-controls="chat-client" onClick={() => setActiveClient('chat')}>Chat</button>
      </div>}
    </header>
    <main className="viewer-main" aria-label="Independent client workspace">
      {clients.loading && <div className="config-state" role="status"><img src="/brand/mark-primary.svg" width="48" height="48" alt="" /><h2>Opening your workspace…</h2><p>Finding your browser and chat apps.</p></div>}
      {clients.error && <div className="config-state" role="alert"><h2>We couldn’t open the client apps.</h2><p>{clients.error}</p><button type="button" className="primary-button" onClick={clients.retry}>Retry loading apps</button></div>}
      {clients.config && <div className="workspace-grid" data-active-client={activeClient}>
        <ClientFrame kind="browser" url={clients.config.browser_url} />
        <ClientFrame kind="chat" url={clients.config.chat_url} />
      </div>}
    </main>
  </div>
}

export default App
