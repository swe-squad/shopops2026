import { useEffect, useReducer, useRef } from 'react'
import { isLocalShop } from './browser-url'
import { ShopClient } from './shop-client'
import { BrowserIcon } from './browser-icon'
import { BrowserTabStrip } from './browser-tab-strip'
import { browserTabsReducer, initialBrowserTabs } from './browser-tabs'

export function BrowserPane({ token, requestedUrl }: { token: string; requestedUrl: { url: string; sequence: number } | null }) {
  const [state, dispatch] = useReducer(browserTabsReducer, undefined, initialBrowserTabs)
  const receivedSequence = useRef(0)
  const active = state.tabs.find(tab => tab.id === state.activeId)!
  const current = active.history[active.index]
  const activeUrl = new URL(current)

  useEffect(() => {
    // The reducer resolves the active tab when a new mailbox event arrives.
    if (requestedUrl && requestedUrl.sequence > receivedSequence.current) {
      receivedSequence.current = requestedUrl.sequence
      dispatch({ type: 'navigate', value: requestedUrl.url })
    }
  }, [requestedUrl])

  return <section className="browser-client" aria-label="Shop browser">
    <div className="browser-window">
      <BrowserTabStrip state={state} dispatch={dispatch} />
      <div className="browser-toolbar">
        <div className="browser-navigation">
          <button className="icon-button" aria-label="Go back" title="Go back" disabled={active.index === 0} onClick={() => dispatch({ type: 'move', offset: -1 })}><BrowserIcon name="back" /></button>
          <button className="icon-button" aria-label="Go forward" title="Go forward" disabled={active.index === active.history.length - 1} onClick={() => dispatch({ type: 'move', offset: 1 })}><BrowserIcon name="forward" /></button>
          <button className="icon-button" aria-label="Reload page" title="Reload page" onClick={() => dispatch({ type: 'reload' })}><BrowserIcon name="reload" /></button>
        </div>
        <form className="address-form" onSubmit={event => { event.preventDefault(); dispatch({ type: 'navigate', value: active.address }) }}>
          <span className="address-icon"><BrowserIcon name={isLocalShop(activeUrl) ? 'lock' : 'globe'} /></span>
          <label className="sr-only" htmlFor="browser-address">Browser address</label>
          <input id="browser-address" type="text" spellCheck={false} autoComplete="off" value={active.address} onChange={event => dispatch({ type: 'address', value: event.target.value })} aria-invalid={!!active.error} aria-describedby={active.error ? 'browser-address-error' : undefined} />
          <button type="submit" className="icon-button address-go" aria-label="Open address" title="Open address"><BrowserIcon name="arrow" /></button>
        </form>
        <button className="icon-button browser-home" aria-label="Go to shop overview" title="Go to shop overview" onClick={() => dispatch({ type: 'navigate', value: '/shop/overview' })}><BrowserIcon name="home" /></button>
        <a className="icon-button open-new-tab" href={current} target="_blank" rel="noopener noreferrer" aria-label="Open in new tab" title="Open in new tab"><BrowserIcon name="external" /></a>
      </div>
      {active.error && <p id="browser-address-error" className="browser-error" role="alert">{active.error}</p>}
      <div className="browser-content">
        {state.tabs.map(tab => {
          const url = new URL(tab.history[tab.index])
          const localShop = isLocalShop(url)
          const external = url.origin !== window.location.origin
          return <div key={tab.id} id={`browser-panel-${tab.id}`} className="browser-tab-panel" role="tabpanel" aria-labelledby={`browser-tab-${tab.id}`} hidden={tab.id !== state.activeId} tabIndex={0}>
            <div className="local-shop-page" hidden={!localShop}>
              <ShopClient token={token} url={new URL(tab.shopUrl)} reload={tab.reload} active={tab.id === state.activeId && localShop} onNavigate={value => dispatch({ type: 'navigate', value, id: tab.id })} />
            </div>
            {external ? <div className="external-page">
              <div className="external-notice"><BrowserIcon name="globe" /><p><strong>{url.hostname}</strong> · External preview. Some websites block embedding. Use “Open in new tab” if the page stays blank.</p></div>
              <iframe key={`${tab.history[tab.index]}-${tab.reload}`} title={`Website: ${url.hostname}`} src={url.href} sandbox="allow-scripts allow-forms" referrerPolicy="no-referrer" />
            </div> : !localShop && <div className="unavailable-page"><span className="empty-symbol"><BrowserIcon name="globe" /></span><h2>This workspace page cannot be opened here.</h2><p>Open a shop page or enter an external website address.</p><button className="secondary-button" onClick={() => dispatch({ type: 'navigate', value: '/shop/overview', id: tab.id })}>Go to shop overview</button></div>}
          </div>
        })}
      </div>
    </div>
  </section>
}
