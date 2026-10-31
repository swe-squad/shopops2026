import { useEffect, useId, useRef } from 'react'
import { BrowserIcon } from './browser-icon'
import { platforms, type MockConnectors, type Platform } from './use-mock-connectors'

export function ConnectionsPage({ page, data, active, reload, onNavigate }: {
  page: 'list' | Platform; data: MockConnectors; active: boolean; reload: number; onNavigate: (url: string) => void
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  const visible = useRef(false)
  const prefix = useId()
  const { refresh } = data
  useEffect(() => {
    visible.current = active
    if (active) void refresh()
    return () => { visible.current = false }
  }, [active, page, reload, refresh])
  useEffect(() => { if (visible.current) heading.current?.focus() }, [page])

  const connect = async (platform: Platform) => {
    if (await data.connect(platform) && visible.current) onNavigate(`/shop/connections/${platform}/success`)
  }
  const connected = page !== 'list' && data.connections?.find(item => item.platform === page)?.connected
  return <div className="shop-page-inner connections-page">
    <div className="connections-heading"><span className="demo-badge">Demo</span><h1 ref={heading} tabIndex={-1}>{page === 'list' ? 'Connect your stores' : `${platforms[page]} connection`}</h1><p className="muted">Try the connection flow. Store data is not synced in this demo.</p></div>
    {data.pending === 'checking' && <p className="incident-loading" role="status">Checking connections…</p>}
    {data.error && <div className="inline-error" role="alert"><p>{data.error}</p><button className="text-button" onClick={() => void refresh()}>Check again</button></div>}
    {page === 'list' ? <>
      <div className="connector-grid">{(Object.keys(platforms) as Platform[]).map(platform => {
        const item = data.connections?.find(connection => connection.platform === platform)
        return <section className="connector-card" key={platform} aria-labelledby={`${prefix}-${platform}`}>
          <div className="connector-card-heading"><span className={`platform-mark platform-${platform}`} aria-hidden="true">{platforms[platform][0]}</span><h2 id={`${prefix}-${platform}`}>{platforms[platform]}</h2></div>
          <p className={item?.connected ? 'connector-status is-connected' : 'connector-status'}>{item?.connected && <BrowserIcon name="check" />}{!item ? 'Not checked' : item.connected ? 'Connected' : 'Not connected'}</p>
          <button type="button" className={item?.connected ? 'secondary-button' : 'primary-button'} disabled={!!data.pending || !item} onClick={() => item?.connected ? onNavigate(`/shop/connections/${platform}/success`) : void connect(platform)}>
            {data.pending === platform ? 'Connecting…' : item?.connected ? `View ${platforms[platform]} connection` : `Log in to ${platforms[platform]}`}<BrowserIcon name="arrow" />
          </button>
        </section>
      })}</div>
      <button className="text-button" onClick={() => onNavigate('/shop/overview')}>Continue to overview<BrowserIcon name="arrow" /></button>
    </> : <>
      {!data.pending && !data.error && data.connections && <section className="connection-result" role="status">
        <span className="empty-symbol"><BrowserIcon name={connected ? 'check' : 'globe'} /></span>
        <h2>{connected ? 'Connection successful' : 'Not connected yet'}</h2>
        <p>{connected ? `${platforms[page]} is connected for this demo. No store data has been imported.` : `Go back to connect ${platforms[page]} in the demo.`}</p>
      </section>}
      <button className="secondary-button" onClick={() => onNavigate('/shop/connections')}><BrowserIcon name="back" />Back to connections</button>
    </>}
  </div>
}
