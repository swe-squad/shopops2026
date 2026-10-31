import { browserUrl, isLocalShop } from './browser-url'

export type BrowserTab = {
  id: number
  history: string[]
  index: number
  address: string
  error: string
  reload: number
  shopUrl: string
}

export type BrowserTabs = { tabs: BrowserTab[]; activeId: number; nextId: number }
export type BrowserAction =
  | { type: 'add' }
  | { type: 'select'; id: number }
  | { type: 'close'; id: number }
  | { type: 'address'; value: string }
  | { type: 'navigate'; value: string; id?: number }
  | { type: 'move'; offset: number }
  | { type: 'reload' }

function createTab(id: number, value = '/shop/overview'): BrowserTab {
  const url = browserUrl(value) ?? new URL('/shop/overview', window.location.origin).href
  return { id, history: [url], index: 0, address: url, error: '', reload: 0, shopUrl: url }
}

export function initialBrowserTabs(): BrowserTabs {
  const location = new URL(window.location.href)
  return { tabs: [createTab(1, isLocalShop(location) ? location.href : undefined)], activeId: 1, nextId: 2 }
}

export function tabTitle(tab: BrowserTab) {
  const url = new URL(tab.history[tab.index])
  if (!isLocalShop(url)) return url.origin === window.location.origin ? 'Workspace page' : url.hostname
  return url.pathname === '/shop/incidents' ? 'Incidents' : ['/shop', '/shop/', '/shop/overview'].includes(url.pathname) ? 'Overview' : 'Shop page'
}

export function browserTabsReducer(state: BrowserTabs, action: BrowserAction): BrowserTabs {
  if (action.type === 'add') {
    return { tabs: [...state.tabs, createTab(state.nextId)], activeId: state.nextId, nextId: state.nextId + 1 }
  }
  if (action.type === 'select') return state.tabs.some(tab => tab.id === action.id) ? { ...state, activeId: action.id } : state
  if (action.type === 'close') {
    const index = state.tabs.findIndex(tab => tab.id === action.id)
    if (index < 0) return state
    const tabs = state.tabs.filter(tab => tab.id !== action.id)
    if (!tabs.length) return { tabs: [createTab(state.nextId)], activeId: state.nextId, nextId: state.nextId + 1 }
    return { ...state, tabs, activeId: state.activeId === action.id ? tabs[Math.min(index, tabs.length - 1)].id : state.activeId }
  }
  const target = action.type === 'navigate' ? action.id ?? state.activeId : state.activeId
  return { ...state, tabs: state.tabs.map(tab => {
    if (tab.id !== target) return tab
    if (action.type === 'address') return { ...tab, address: action.value }
    if (action.type === 'reload') return { ...tab, reload: tab.reload + 1, address: tab.history[tab.index], error: '' }
    if (action.type === 'move') {
      const index = tab.index + action.offset
      if (index < 0 || index >= tab.history.length) return tab
      const url = tab.history[index]
      return { ...tab, index, address: url, error: '', shopUrl: isLocalShop(new URL(url)) ? url : tab.shopUrl }
    }
    const url = browserUrl(action.value)
    if (!url) return { ...tab, error: 'Enter an http or https URL, or a local shop path.' }
    const history = url === tab.history[tab.index] ? tab.history : [...tab.history.slice(0, tab.index + 1), url]
    const index = url === tab.history[tab.index] ? tab.index : history.length - 1
    return { ...tab, history, index, address: url, error: '', shopUrl: isLocalShop(new URL(url)) ? url : tab.shopUrl }
  }) }
}
