import { useEffect, useId, useRef } from 'react'
import { BrowserIcon } from './browser-icon'
import { IncidentFeed } from './incident-feed'
import { IncidentForm } from './incident-form'
import { useIncidents } from './use-incidents'

export function ShopClient({ token, url, onNavigate, reload = 0, active = true }: { token: string; url: URL; onNavigate: (url: string) => void; reload?: number; active?: boolean }) {
  const data = useIncidents(token, reload)
  const prefix = useId()
  const page = useRef<HTMLDivElement>(null)
  const previousPath = useRef(url.pathname)
  const scrolledTarget = useRef('')
  const knownPage = ['/shop', '/shop/', '/shop/overview', '/shop/incidents'].includes(url.pathname)
  const incidentsPage = url.pathname === '/shop/incidents'
  const shownIncidents = incidentsPage || url.hash ? data.incidents : data.incidents.slice(0, 5)

  useEffect(() => {
    if (url.pathname !== previousPath.current) {
      if (page.current) page.current.scrollTop = 0
      previousPath.current = url.pathname
    }
    const match = /^#incident-(\d+)$/.exec(url.hash)
    const target = `${url.pathname}${url.hash}`
    if (!match) scrolledTarget.current = ''
    if (active && match && !data.loading && scrolledTarget.current !== target) {
      const container = page.current
      const incident = container?.querySelector<HTMLElement>(`[data-incident-id="${match[1]}"]`)
      if (container && incident) {
        // Scroll only shop content; browser chrome and its embedding viewer stay fixed.
        container.scrollTop += incident.getBoundingClientRect().top - container.getBoundingClientRect().top
        scrolledTarget.current = target
      }
    }
  }, [url.pathname, url.hash, data.loading, active])

  return <section className="shop-client" aria-label="Shop workspace">
    <nav className="shop-nav" aria-label="Shop pages">{[['Overview', '/shop/overview'], ['Incidents', '/shop/incidents']].map(([label, path]) => <a key={path} href={path} aria-current={(incidentsPage ? path === '/shop/incidents' : knownPage && path === '/shop/overview') ? 'page' : undefined} onClick={event => { if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(path) } }}>{label}</a>)}<span className="workspace-mode">Manual workspace</span></nav>
    <div className="shop-page" ref={page} tabIndex={0} aria-label="Shop page content">
      {!knownPage ? <div className="unavailable-page"><span className="empty-symbol"><BrowserIcon name="globe" /></span><h1>This shop page is not available.</h1><p>Choose a workspace page to continue.</p><button className="secondary-button" onClick={() => onNavigate('/shop/overview')}>Go to overview</button></div> : <div className="shop-page-inner">
        <h1>{incidentsPage ? 'Incident log' : 'Shop overview'}</h1>
        <aside className="connection-note"><BrowserIcon name="list" /><p>Shop data is not connected. Add incidents manually.</p></aside>
        <div className="operations-grid">
          <section className="incidents-section" aria-labelledby={`${prefix}-incidents`}>
            <div className="section-heading"><div><h2 id={`${prefix}-incidents`}>{incidentsPage ? 'Incidents' : 'Recent incidents'}</h2><p className="muted">{data.loading ? 'Getting your workspace records.' : data.incidents.length ? `${data.incidents.length} recent ${data.incidents.length === 1 ? 'record' : 'records'}` : 'Keep important details within reach.'}</p></div><button className="text-button" disabled={data.loading || data.saving} onClick={data.refresh}><BrowserIcon name="reload" />Refresh</button></div>
            <IncidentFeed incidents={shownIncidents} loading={data.loading} error={data.loadError} onRetry={data.refresh} prefix={prefix} />
            {!incidentsPage && data.incidents.length > 5 && <button className="text-button view-incidents" onClick={() => onNavigate('/shop/incidents')}>View all recent incidents <BrowserIcon name="arrow" /></button>}
          </section>
          <IncidentForm saving={data.saving} error={data.saveError} onSave={data.addIncident} />
        </div>
      </div>}
    </div>
  </section>
}
