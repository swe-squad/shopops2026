import { BrowserIcon } from './browser-icon'
import { parseIncidentTime } from './workspace-api'
import type { Incident } from './workspace-api'

function IncidentTime({ value }: { value: string }) {
  const timestamp = parseIncidentTime(value)
  return <time dateTime={timestamp.toISOString()}>{timestamp.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</time>
}

export function IncidentFeed({ incidents, loading, error, onRetry, prefix }: { incidents: Incident[]; loading: boolean; error: string; onRetry: () => void; prefix: string }) {
  if (loading) return <div className="incident-loading" role="status"><p>Loading incidents…</p><div className="skeleton-row" aria-hidden="true" /><div className="skeleton-row" aria-hidden="true" /><div className="skeleton-row" aria-hidden="true" /></div>
  return <>
    {error && <div className="inline-error" role="alert"><h3>Incidents could not be refreshed</h3><p>{error}</p><button className="text-button" onClick={onRetry}>Retry loading incidents</button></div>}
    {!error && incidents.length === 0 && <div className="empty-incidents"><span className="empty-symbol"><BrowserIcon name="list" /></span><h3>No incidents yet</h3><p>When something needs attention, record it here. Add your first incident to get started.</p><span className="empty-caption">Your workspace is ready.</span></div>}
    {incidents.length > 0 && <div className="incident-list">{incidents.map(incident => <article key={incident.id} id={`${prefix}-incident-${incident.id}`} data-incident-id={incident.id} className="incident-record" tabIndex={-1}>
      <div className="incident-record-top"><span className="incident-number">#{incident.id}</span><IncidentTime value={incident.created_at} /></div>
      <h3>{incident.title}</h3>{incident.detail ? <p>{incident.detail}</p> : <p className="muted">No additional details.</p>}
    </article>)}</div>}
    {incidents.length === 100 && <p className="incident-limit-note">Showing the 100 most recent incidents.</p>}
  </>
}
