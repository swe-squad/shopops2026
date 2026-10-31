import { ClientFrame } from './client-frame'
import { useClientConfig } from './use-client-config'

function App() {
  const clients = useClientConfig()

  return <div className="viewer">
    <header className="viewer-header"><a className="brand" href="/" aria-label="ShopOps workspace"><span className="brand-mark" aria-hidden="true">✳</span><span>shopops<span className="brand-period">.</span></span></a><span className="header-divider" aria-hidden="true" /><span className="workspace-label">Workspace</span><span className="header-note">A little clarity for your day.</span></header>
    <main className="viewer-main">
      <div className="viewer-intro"><div><span className="eyebrow">YOUR SHOP, ON TRACK</span><h1>Two perspectives. One workspace.</h1></div><p>Unlock each app separately.<br />Reloading resets only that app’s session.</p></div>
      {clients.loading && <div className="config-state" role="status"><span className="state-symbol" aria-hidden="true">◫</span><h2>Opening your workspace…</h2><p>Finding your browser and chat apps.</p></div>}
      {clients.error && <div className="config-state config-error" role="alert"><span className="state-symbol" aria-hidden="true">!</span><h2>We couldn’t open the client apps.</h2><p>{clients.error}</p><button type="button" className="primary-button" onClick={clients.retry}>Retry loading apps</button></div>}
      {clients.config && <div className="workspace-grid"><ClientFrame kind="browser" url={clients.config.browser_url} /><ClientFrame kind="chat" url={clients.config.chat_url} /></div>}
      {clients.config && <footer className="viewer-footer"><span>Shop and chat keep their own sessions.</span><span>Can’t see an app? Open it in a new tab ↗</span></footer>}
    </main>
  </div>
}

export default App
