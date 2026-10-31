import { useState } from 'react'

type ClientFrameProps = { kind: 'browser' | 'chat'; url: string }

export function ClientFrame({ kind, url }: ClientFrameProps) {
  const [revision, setRevision] = useState(0)
  const browser = kind === 'browser'
  const name = browser ? 'Shop browser' : 'Agent chat'

  return <section id={`${kind}-client`} className={`client-panel ${browser ? 'browser-panel' : 'chat-panel'}`} aria-label={`${name} client`}>
    <div className="client-toolbar">
      <div className="client-title">
        <h2>{name}</h2>
      </div>
      <div className="client-actions">
        <button type="button" className="icon-button" onClick={() => setRevision(value => value + 1)} aria-label={`Reload ${browser ? 'browser' : 'chat'} app`} title={`Reload ${name.toLowerCase()}; its session will reset`}>↻</button>
        <a className="icon-button" href={url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${browser ? 'browser' : 'chat'} app in new tab`} title="Open in new tab">↗</a>
      </div>
    </div>
    <div className={browser ? 'browser-window' : 'phone-window'}>
      <iframe key={revision} title={`${name} app`} src={url} sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox" referrerPolicy="no-referrer" />
    </div>
  </section>
}
