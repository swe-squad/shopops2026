import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { authHeaders, checkResponse } from './workspace-api'
import type { Incident } from './workspace-api'

export function ShopClient({ token, url, onNavigate }: { token: string; url: URL; onNavigate: (url: string) => void }) {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [title, setTitle] = useState('')
  const [detail, setDetail] = useState('')
  const [refresh, setRefresh] = useState(0)
  const saveController = useRef<AbortController | null>(null)
  const knownPage = ['/shop', '/shop/', '/shop/overview', '/shop/incidents'].includes(url.pathname)

  useEffect(() => {
    const controller = new AbortController()
    void (async () => {
      try {
        const response = await fetch('/api/operations/incidents', { headers: authHeaders(token), signal: controller.signal })
        await checkResponse(response, 'Could not load incidents')
        const data = await response.json() as Incident[]
        if (!controller.signal.aborted) setIncidents(data)
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not load incidents.')
      } finally { if (!controller.signal.aborted) setLoading(false) }
    })()
    return () => controller.abort()
  }, [token, refresh])

  useEffect(() => () => { saveController.current?.abort(); saveController.current = null }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!title.trim() || saveController.current) return
    const controller = new AbortController()
    saveController.current = controller
    setSaving(true)
    setError('')
    try {
      const response = await fetch('/api/operations/incidents', {
        method: 'POST', headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), detail: detail.trim() }), signal: controller.signal,
      })
      await checkResponse(response, 'Could not add the incident')
      const incident = await response.json() as Incident
      if (!controller.signal.aborted) { setIncidents(items => [incident, ...items].slice(0, 100)); setTitle(''); setDetail('') }
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not add the incident.')
    } finally {
      if (saveController.current === controller) { saveController.current = null; setSaving(false) }
    }
  }

  return <section className="shop-client" aria-label="Shop workspace">
    <header className="shop-topbar"><div className="shop-wordmark"><span aria-hidden="true">✳</span> shopops<span className="wordmark-period">.</span></div><span className="shop-workspace-label">SELLER WORKSPACE</span></header>
    <nav className="shop-nav" aria-label="Shop pages">{[['Overview', '/shop/overview'], ['Incidents', '/shop/incidents']].map(([label, path]) => <a key={path} href={path} aria-current={url.pathname === path ? 'page' : undefined} onClick={event => { event.preventDefault(); onNavigate(path) }}>{label}</a>)}</nav>
    {!knownPage ? <div className="shop-page"><h1>This shop page is not available.</h1><p className="muted">Choose a workspace page to continue.</p><button className="secondary-button" onClick={() => onNavigate('/shop/overview')}>Go to overview</button></div> : <div className="shop-page">
      <div className="eyebrow">YOUR OPERATIONS WORKSPACE</div><h1>Your shop, in view.</h1><p className="muted page-description">Track the issues that need your attention.</p>
      <aside className="connection-note"><span aria-hidden="true">◫</span><div><strong>Manual workspace</strong><p>Shop data is not connected. Add incidents to track them here.</p></div></aside>
      <div className="section-heading"><div><span className="eyebrow">NEEDS YOUR ATTENTION</span><h2>Incidents</h2></div><button className="text-button" disabled={loading || saving} onClick={() => { setLoading(true); setError(''); setRefresh(value => value + 1) }}>Refresh</button></div>
      {error && <div className="inline-error" role="alert"><p>{error}</p><button className="text-button" disabled={saving || loading} onClick={() => { setLoading(true); setError(''); setRefresh(value => value + 1) }}>Retry loading incidents</button></div>}
      {loading && <p className="loading-note" role="status">Loading incidents…</p>}
      {!loading && !error && incidents.length === 0 && <div className="empty-incidents"><span aria-hidden="true">☷</span><h3>No incidents yet</h3><p>Add an incident below to start tracking it.</p></div>}
      <div className="incident-list">{incidents.map(incident => <article key={incident.id} id={`incident-${incident.id}`} className="incident-record"><div><h3>{incident.title}</h3><span className="incident-number">#{incident.id}</span></div>{incident.detail && <p>{incident.detail}</p>}<time dateTime={incident.created_at}>{incident.created_at.replace('T', ' ').replace(/Z$/, '')} UTC</time></article>)}</div>
      <form className="incident-form" onSubmit={submit}><div><h2>Add an incident</h2><p className="muted">Keep a clear record of what happened.</p></div><label htmlFor="incident-title">Title</label><input id="incident-title" value={title} onChange={event => setTitle(event.target.value)} maxLength={200} required disabled={saving} /><label htmlFor="incident-detail">Details <span className="muted">(optional)</span></label><textarea id="incident-detail" rows={3} value={detail} onChange={event => setDetail(event.target.value)} maxLength={2000} disabled={saving} /><button type="submit" className="primary-button" disabled={loading || saving || !title.trim()}>{saving ? 'Adding incident…' : 'Add incident'}</button></form>
      <footer className="shop-footer">Keep the details here. Plan your next step with your agent.</footer>
    </div>}
  </section>
}
