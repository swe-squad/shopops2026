import { afterEach, describe, expect, it } from 'vitest'
import { browserTabsReducer, initialBrowserTabs, tabTitle } from './browser-tabs'

afterEach(() => window.history.replaceState(null, '', '/'))

describe('browser navigation history', () => {
  it.each([
    ['/shop/connections', 'Connections'],
    ['/shop/connections/shopee/success', 'Connections'],
    ['/shop/products?shop_key=merchant&sku=ITEM-1', 'Products'],
  ])('preserves direct page entry and title for %s', (path, title) => {
    window.history.replaceState(null, '', path)
    const state = initialBrowserTabs()
    expect(state.tabs[0].address).toBe(`${window.location.origin}${path}`)
    expect(tabTitle(state.tabs[0])).toBe(title)
  })

  it('starts a direct shop deep link in its first tab', () => {
    window.history.replaceState(null, '', '/shop/incidents#incident-7')
    const state = initialBrowserTabs()
    expect(state.tabs[0].address).toBe(`${window.location.origin}/shop/incidents#incident-7`)
    expect(tabTitle(state.tabs[0])).toBe('Incidents')
  })

  it('discards forward history on a new destination and keeps history intact for rejected URLs', () => {
    let state = initialBrowserTabs()
    state = browserTabsReducer(state, { type: 'navigate', value: '/shop/incidents' })
    state = browserTabsReducer(state, { type: 'navigate', value: 'https://example.com/old' })
    state = browserTabsReducer(state, { type: 'move', offset: -1 })
    state = browserTabsReducer(state, { type: 'navigate', value: 'https://example.com/new' })
    const tab = state.tabs[0]
    expect(tab.history).toEqual([
      `${window.location.origin}/shop/connections`, `${window.location.origin}/shop/incidents`, 'https://example.com/new',
    ])
    expect(browserTabsReducer(state, { type: 'move', offset: 1 }).tabs[0]).toEqual(tab)
    for (const value of ['javascript:alert(1)', 'https://user:secret@example.com', 'https://exa\nmple.com/']) {
      const result = browserTabsReducer(state, { type: 'navigate', value })
      expect(result.tabs[0].history).toEqual(tab.history)
      expect(result.tabs[0].index).toBe(tab.index)
      expect(result.tabs[0].error).toBeTruthy()
    }
  })
})
