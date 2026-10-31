import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowserPane } from './browser-pane'
import { catalog, shops } from './test/catalog-fixtures'

const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
const localUrl = (path: string) => `${window.location.origin}${path}`
const panel = () => within(screen.getByRole('tabpanel'))
const address = () => screen.getByRole('textbox', { name: 'Browser address' })

function openAddress(value: string) {
  fireEvent.change(address(), { target: { value } })
  fireEvent.click(screen.getByRole('button', { name: 'Open address' }))
}

async function addTab() {
  fireEvent.click(screen.getByRole('button', { name: 'New browser tab' }))
  await panel().findByText('No incidents yet')
}

beforeEach(() => {
  window.history.replaceState(null, '', '/shop/overview')
  vi.stubGlobal('fetch', vi.fn(async () => json([])))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState(null, '', '/') })

describe('browser tabs', () => {
  it('keeps Connections as the default entry and opens Products independently of demo flags', async () => {
    window.history.replaceState(null, '', '/')
    const fetchMock = vi.fn(async (path: string) => {
      if (path === '/api/mock/connectors') return json({ connections: [
        { platform: 'shopee', connected: false, mock: true },
        { platform: 'tiktok', connected: false, mock: true },
      ] })
      if (path === '/api/operations/catalog/shops') return json(shops)
      if (path.startsWith('/api/operations/catalog?')) return json(catalog)
      return json([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<BrowserPane token="workspace-secret" requestedUrl={null} />)
    await panel().findByRole('button', { name: 'Log in to Shopee' })
    expect(screen.getByRole('tab', { name: 'Connections — tab 1' })).toBeInTheDocument()
    fireEvent.click(panel().getByRole('link', { name: 'Products' }))
    await panel().findByRole('link', { name: /Canvas tote/ })
    expect(screen.getByRole('tab', { name: 'Products — tab 1' })).toBeInTheDocument()
    expect(panel().getByRole('link', { name: 'Connections' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([path]) => path === '/api/mock/connectors/shopee')).toBe(false)
    fireEvent.click(panel().getByRole('link', { name: 'Connections' }))
    await panel().findByRole('button', { name: 'Log in to Shopee' })
    fireEvent.click(screen.getByRole('button', { name: 'Go back' }))
    await panel().findByRole('link', { name: /Canvas tote/ })
  })

  it('keeps independent history, address drafts, and incident drafts when switching tabs', async () => {
    render(<BrowserPane token="workspace-secret" requestedUrl={null} />)
    await panel().findByText('No incidents yet')
    fireEvent.change(panel().getByRole('textbox', { name: 'Title' }), { target: { value: 'First tab draft' } })
    fireEvent.change(panel().getByRole('textbox', { name: /Details/ }), { target: { value: 'Keep this context' } })
    fireEvent.click(panel().getByRole('link', { name: 'Incidents' }))

    await addTab()
    expect(address()).toHaveValue(localUrl('/shop/overview'))
    expect(screen.getByRole('button', { name: 'Go back' })).toBeDisabled()
    expect(panel().getByRole('textbox', { name: 'Title' })).toHaveValue('')
    fireEvent.change(panel().getByRole('textbox', { name: 'Title' }), { target: { value: 'Second tab draft' } })
    fireEvent.change(address(), { target: { value: 'https://example.com/not-submitted' } })

    fireEvent.click(screen.getByRole('tab', { name: 'Incidents — tab 1' }))
    expect(address()).toHaveValue(localUrl('/shop/incidents'))
    expect(panel().getByRole('textbox', { name: 'Title' })).toHaveValue('First tab draft')
    expect(panel().getByRole('textbox', { name: /Details/ })).toHaveValue('Keep this context')
    fireEvent.click(screen.getByRole('button', { name: 'Go back' }))
    expect(address()).toHaveValue(localUrl('/shop/overview'))
    fireEvent.click(screen.getByRole('button', { name: 'Go forward' }))
    expect(address()).toHaveValue(localUrl('/shop/incidents'))

    fireEvent.click(screen.getByRole('tab', { name: 'Overview — tab 2' }))
    expect(address()).toHaveValue('https://example.com/not-submitted')
    expect(panel().getByRole('textbox', { name: 'Title' })).toHaveValue('Second tab draft')
    expect(screen.getByRole('button', { name: 'Go back' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Go forward' })).toBeDisabled()
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('supports roving keyboard focus, wrapping, Home, End, and closing the last tab', async () => {
    render(<BrowserPane token="workspace-secret" requestedUrl={null} />)
    await panel().findByText('No incidents yet')
    await addTab()
    await addTab()
    const tabs = screen.getAllByRole('tab')
    expect(tabs[2]).toHaveFocus()
    expect(tabs.map(tab => tab.tabIndex)).toEqual([-1, -1, 0])
    fireEvent.keyDown(tabs[2], { key: 'Home' })
    expect(tabs[0]).toHaveFocus()
    fireEvent.keyDown(tabs[0], { key: 'ArrowLeft' })
    expect(tabs[2]).toHaveFocus()
    fireEvent.keyDown(tabs[2], { key: 'ArrowRight' })
    expect(tabs[0]).toHaveFocus()
    fireEvent.keyDown(tabs[0], { key: 'End' })
    expect(tabs[2]).toHaveFocus()
    fireEvent.keyDown(tabs[2], { key: 'Delete' })
    expect(tabs[1]).toHaveFocus()
    expect(tabs[2]).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close Overview tab 1' }))
    expect(tabs[1]).toHaveFocus()
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(tabs[1], { key: 'Delete' })
    await panel().findByText('No incidents yet')
    expect(screen.getAllByRole('tab')).toHaveLength(1)
    expect(screen.getByRole('tab')).toHaveFocus()
    expect(screen.getByRole('tab')).not.toBe(tabs[1])
    expect(panel().getByRole('heading', { name: 'Shop overview' })).toBeInTheDocument()
  })

  it('keeps an external iframe mounted while another tab is selected and reloads only its tab', async () => {
    render(<BrowserPane token="workspace-secret" requestedUrl={null} />)
    await panel().findByText('No incidents yet')
    openAddress('https://example.com/tracking')
    const externalFrame = screen.getByTitle('Website: example.com')
    await addTab()
    expect(externalFrame).toBeInTheDocument()
    expect(externalFrame).not.toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Reload page' }))
    await panel().findByText('No incidents yet')
    expect(screen.getByTitle('Website: example.com')).toBe(externalFrame)
    fireEvent.click(screen.getByRole('tab', { name: 'example.com — tab 1' }))
    expect(externalFrame).toBeVisible()
    expect(address()).toHaveValue('https://example.com/tracking')
    fireEvent.click(screen.getByRole('button', { name: 'Reload page' }))
    await act(async () => {})
    expect(screen.getByTitle('Website: example.com')).not.toBe(externalFrame)
  })

  it('opens new mailbox events in the active tab without replaying an old event on tab selection', async () => {
    const view = render(<BrowserPane token="workspace-secret" requestedUrl={null} />)
    await panel().findByText('No incidents yet')
    await addTab()
    view.rerender(<BrowserPane token="workspace-secret" requestedUrl={{ url: '/shop/incidents#incident-7', sequence: 7 }} />)
    expect(address()).toHaveValue(localUrl('/shop/incidents#incident-7'))
    fireEvent.click(screen.getByRole('tab', { name: 'Overview — tab 1' }))
    view.rerender(<BrowserPane token="workspace-secret" requestedUrl={{ url: '/shop/incidents#incident-7', sequence: 7 }} />)
    expect(address()).toHaveValue(localUrl('/shop/overview'))
    expect(screen.getByRole('button', { name: 'Go back' })).toBeDisabled()
    view.rerender(<BrowserPane token="workspace-secret" requestedUrl={{ url: 'https://example.com/orders', sequence: 8 }} />)
    expect(address()).toHaveValue('https://example.com/orders')
    fireEvent.click(screen.getByRole('tab', { name: 'Incidents — tab 2' }))
    expect(address()).toHaveValue(localUrl('/shop/incidents#incident-7'))
  })

  it('retains content scroll after returning to a tab with an incident deep link', async () => {
    const incident = { id: 7, title: 'Carrier handoff', detail: '', created_at: '2026-10-31T09:00:00Z' }
    vi.stubGlobal('fetch', vi.fn(async () => json([incident])))
    render(<BrowserPane token="workspace-secret" requestedUrl={{ url: '/shop/incidents#incident-7', sequence: 7 }} />)
    await panel().findByRole('heading', { name: incident.title })
    const content = panel().getByLabelText('Shop page content')
    content.scrollTop = 180
    // A different position would cause a repeated deep-link scroll to move the reader.
    vi.spyOn(content, 'getBoundingClientRect').mockReturnValue({ top: 100 } as DOMRect)
    fireEvent.click(screen.getByRole('button', { name: 'New browser tab' }))
    await panel().findByRole('heading', { name: incident.title })
    fireEvent.click(screen.getByRole('tab', { name: 'Incidents — tab 1' }))
    expect(content.scrollTop).toBe(180)
  })
})
