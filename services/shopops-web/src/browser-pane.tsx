import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { browserUrl, isLocalShop } from './browser-url'
import { ShopClient } from './shop-client'

export function BrowserPane({ token, requestedUrl }: { token: string; requestedUrl: { url: string; sequence: number } | null }) {
  const [navigation, setNavigation] = useState(() => ({
    history: [new URL(isLocalShop(new URL(window.location.href)) ? window.location.href : '/shop/overview', window.location.origin).href],
    index: 0,
  }))
  const { history, index } = navigation
  const [address, setAddress] = useState(history[0])
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const addressInput = useRef<HTMLInputElement>(null)
  const current = history[index]
  const url = new URL(current)
  const localShop = isLocalShop(url)
  const external = url.origin !== window.location.origin

  const navigate = useCallback((value: string) => {
    const next = browserUrl(value)
    if (!next) { setError('Enter an http or https URL, or a local shop path.'); return }
    setNavigation(previous => ({ history: [...previous.history.slice(0, previous.index + 1), next], index: previous.index + 1 }))
    setAddress(next)
    setError('')
  }, [])

  useEffect(() => {
    // A link in the separate chat client is an external navigation request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (requestedUrl) navigate(requestedUrl.url)
  }, [requestedUrl, navigate])

  function move(next: number) { setNavigation(previous => ({ ...previous, index: next })); setAddress(history[next]); setError('') }
  function submit(event: FormEvent) { event.preventDefault(); navigate(address); addressInput.current?.blur() }

  return <section className="browser-client" aria-label="Shop browser">
    <div className="pane-heading"><div><span className="eyebrow">THE DETAILS, IN VIEW</span><h2>Shop browser</h2></div><span className="pane-index">01</span></div>
    <div className="browser-window">
      <div className="browser-tab"><span className="tab-mark" aria-hidden="true">◫</span><span>{localShop ? 'ShopOps · Seller workspace' : url.hostname}</span><a className="new-tab-link" href={current} target="_blank" rel="noopener noreferrer">Open in new tab ↗</a></div>
      <div className="browser-toolbar"><div className="browser-navigation"><button className="icon-button" aria-label="Go back" title="Go back" disabled={index === 0} onClick={() => move(index - 1)}>←</button><button className="icon-button" aria-label="Go forward" title="Go forward" disabled={index === history.length - 1} onClick={() => move(index + 1)}>→</button><button className="icon-button" aria-label="Reload page" title="Reload page" onClick={() => setReloadKey(value => value + 1)}>↻</button></div><form className="address-form" onSubmit={submit}><label className="sr-only" htmlFor="browser-address">Browser address</label><input id="browser-address" ref={addressInput} type="text" spellCheck={false} value={address} onChange={event => setAddress(event.target.value)} /><button type="submit" className="address-go" aria-label="Open address">↵</button></form><button className="icon-button browser-home" aria-label="Go to shop overview" title="Go to shop overview" onClick={() => navigate('/shop/overview')}>⌂</button></div>
      {error && <p className="browser-error" role="alert">{error}</p>}
      {external && <div className="external-notice"><span><strong>{url.hostname}</strong> · Some websites cannot be embedded. External pages use a restricted frame.</span></div>}
      <div className="browser-content" key={reloadKey}>
        {localShop ? <ShopClient token={token} url={url} onNavigate={navigate} /> : external ? <iframe title={`Website: ${url.hostname}`} src={current} sandbox="allow-scripts allow-forms" referrerPolicy="no-referrer" /> : <div className="unavailable-page"><h3>This workspace page cannot be opened here.</h3><p>Open a shop page or enter an external website address.</p><button className="secondary-button" onClick={() => navigate('/shop/overview')}>Go to shop overview</button></div>}
      </div>
    </div>
  </section>
}
