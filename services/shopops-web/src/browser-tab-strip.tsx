import { useEffect, useRef } from 'react'
import type { Dispatch, KeyboardEvent } from 'react'
import { BrowserIcon } from './browser-icon'
import { tabTitle } from './browser-tabs'
import type { BrowserAction, BrowserTabs } from './browser-tabs'

export function BrowserTabStrip({ state, dispatch }: { state: BrowserTabs; dispatch: Dispatch<BrowserAction> }) {
  const list = useRef<HTMLDivElement>(null)
  const focusRequested = useRef(false)
  useEffect(() => {
    if (focusRequested.current) {
      list.current?.querySelector<HTMLButtonElement>(`#browser-tab-${state.activeId}`)?.focus()
      focusRequested.current = false
    }
  }, [state.activeId, state.tabs.length])

  function update(action: BrowserAction) { focusRequested.current = true; dispatch(action) }
  function keyboard(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number | undefined
    if (event.key === 'ArrowRight') next = (index + 1) % state.tabs.length
    if (event.key === 'ArrowLeft') next = (index - 1 + state.tabs.length) % state.tabs.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = state.tabs.length - 1
    if (next !== undefined) { event.preventDefault(); update({ type: 'select', id: state.tabs[next].id }) }
    if (event.key === 'Delete') { event.preventDefault(); update({ type: 'close', id: state.tabs[index].id }) }
  }

  return <div className="browser-tabs-bar">
    <div ref={list} className="browser-tabs" role="tablist" aria-label="Browser tabs">
      {state.tabs.map((tab, index) => <div key={tab.id} className={`browser-tab-item${state.activeId === tab.id ? ' is-active' : ''}`} role="presentation">
        <button id={`browser-tab-${tab.id}`} role="tab" aria-selected={state.activeId === tab.id} aria-controls={`browser-panel-${tab.id}`} aria-label={`${tabTitle(tab)} — tab ${index + 1}`} tabIndex={state.activeId === tab.id ? 0 : -1} className="browser-tab-button" onClick={() => dispatch({ type: 'select', id: tab.id })} onKeyDown={event => keyboard(event, index)} title={tabTitle(tab)}>
          <img src="/brand/mark-primary.svg" alt="" width="18" height="18" /><span>{tabTitle(tab)}</span>
        </button>
        <button className="tab-close" aria-label={`Close ${tabTitle(tab)} tab ${index + 1}`} tabIndex={state.activeId === tab.id ? 0 : -1} onClick={() => update({ type: 'close', id: tab.id })} title="Close tab"><BrowserIcon name="close" /></button>
      </div>)}
    </div>
    <button className="icon-button add-tab" onClick={() => update({ type: 'add' })} aria-label="New browser tab" title="New browser tab"><BrowserIcon name="plus" /></button>
  </div>
}
