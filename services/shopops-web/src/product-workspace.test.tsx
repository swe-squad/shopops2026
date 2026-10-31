import { useState } from 'react'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ProductWorkspace } from './product-workspace'
import { ShopClient } from './shop-client'
import type { MockConnectors } from './use-mock-connectors'
import { productUrl } from './catalog-api'
import { catalog, detail, json, product, shops } from './test/catalog-fixtures'

function Workspace({ initial = productUrl(product.shop_key) }: { initial?: string }) {
  const [path, setPath] = useState(initial)
  return <><output aria-label="Current product address">{path}</output><ProductWorkspace token="workspace-secret" url={new URL(path, window.location.origin)} active reload={0} onNavigate={setPath} /></>
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => json(path.endsWith('/shops') ? shops : path.includes('/product?') ? detail : catalog)))
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('merchant product workspace', () => {
  it('searches real records, navigates encoded deep links, and scopes inspection drafts', async () => {
    render(<Workspace />)
    const tile = await screen.findByRole('link', { name: /Canvas tote/ })
    expect(tile).toHaveAttribute('href', '/shop/products?shop_key=shop%2Fa&sku=SKU%2FA+1')
    expect(within(tile).getByText('No product image')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search products by name or SKU' }), { target: { value: 'missing' } })
    expect(screen.getByRole('heading', { name: 'No matching products' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }))
    fireEvent.click(screen.getByRole('link', { name: /Canvas tote/ }))
    const summary = await screen.findByRole('region', { name: 'Product details' })
    expect(within(summary).getByText(/Not a current listing price/)).toBeInTheDocument()
    expect(screen.getByLabelText('Current product address')).toHaveTextContent('sku=SKU%2FA+1')
    fireEvent.click(screen.getByRole('button', { name: 'Prepare question draft' }))
    expect((screen.getByRole('textbox', { name: 'Investigation question · draft only' }) as HTMLTextAreaElement).value).toContain('shop shop/a, SKU SKU/A 1')
    fireEvent.change(screen.getByRole('textbox', { name: 'Investigation question · draft only' }), { target: { value: 'Keep my investigation context' } })
    fireEvent.click(screen.getByRole('link', { name: 'All products' }))
    fireEvent.click(await screen.findByRole('link', { name: /Canvas tote/ }))
    expect(await screen.findByRole('textbox', { name: 'Investigation question · draft only' })).toHaveValue('Keep my investigation context')
    expect(vi.mocked(fetch).mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true)
    expect(window.localStorage.getItem('token')).toBeNull()
  })

  it('opens a product deep link directly and supports evidence tabs by keyboard', async () => {
    render(<Workspace initial={productUrl(product.shop_key, product.sku)} />)
    await screen.findByText('Seam came loose.')
    expect(fetch).toHaveBeenCalledWith('/api/operations/catalog/product?shop_key=shop%2Fa&sku=SKU%2FA+1', expect.objectContaining({ headers: { Authorization: 'Bearer workspace-secret' } }))
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Reviews 1' }), { key: 'End' })
    const returns = screen.getByRole('tab', { name: 'Related returns 1' })
    expect(returns).toHaveFocus()
    expect(returns).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('Damaged seam')).toBeVisible()
    expect(screen.getByText(/does not confirm that this SKU was returned/)).toBeVisible()
    fireEvent.keyDown(returns, { key: 'ArrowLeft' })
    expect(screen.getByRole('tab', { name: 'Related orders 1' })).toHaveFocus()
    expect(screen.getByText('completed')).toBeVisible()
  })

  it('changes shops through the URL without carrying the previous shop’s products', async () => {
    vi.stubGlobal('fetch', vi.fn(async (path: string) => path.includes('shop_key=other') ? json({ ...catalog, shop: shops.shops[1], products: [] }) : json(path.endsWith('/shops') ? shops : catalog)))
    render(<Workspace />)
    await screen.findByRole('link', { name: /Canvas tote/ })
    fireEvent.change(screen.getByRole('combobox', { name: 'Shop' }), { target: { value: 'other' } })
    expect(screen.queryByRole('link', { name: /Canvas tote/ })).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'No products observed' })).toBeInTheDocument()
    expect(screen.getByLabelText('Current product address')).toHaveTextContent('shop_key=other')
  })

  it('shows disconnected source errors and retry without fixture products', async () => {
    const fetchMock = vi.fn(async () => new Response('', { status: 503 }))
    vi.stubGlobal('fetch', fetchMock)
    render(<Workspace />)
    expect(await screen.findByText('Product data unavailable')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Canvas tote/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await act(async () => {})
    expect(fetchMock.mock.calls.length).toBeGreaterThan(2)
  })

  it('keeps last good products visible and explicitly marks a failed refresh', async () => {
    let failure = false
    vi.stubGlobal('fetch', vi.fn(async (path: string) => failure ? new Response('', { status: 503 }) : json(path.endsWith('/shops') ? shops : catalog)))
    render(<Workspace />)
    await screen.findByRole('link', { name: /Canvas tote/ })
    failure = true
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(await screen.findByText('Showing last good data · refresh failed')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Canvas tote/ })).toBeInTheDocument()
  })

  it.each([401, 403, 404])('removes product evidence after the server rejects a previously successful selection (%s)', async status => {
    let revoked = false
    vi.stubGlobal('fetch', vi.fn(async (path: string) => path.endsWith('/shops') ? json(shops) : revoked ? new Response('', { status }) : json(detail)))
    render(<Workspace initial={productUrl(product.shop_key, product.sku)} />)
    await screen.findByText('Seam came loose.')
    revoked = true
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(await screen.findByText('Product data unavailable')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Product details' })).not.toBeInTheDocument()
    expect(screen.queryByText('Seam came loose.')).not.toBeInTheDocument()
    expect(screen.queryByText('Showing last good data · refresh failed')).not.toBeInTheDocument()
  })

  it('shows an empty authorized shop list without a perpetual product loading state', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ ...shops, shops: [] })))
    render(<Workspace initial="/shop/products" />)
    expect(await screen.findByRole('heading', { name: 'No shops available' })).toBeInTheDocument()
    expect(screen.queryByText('Loading your products…')).not.toBeInTheDocument()
  })

  it('opens a selected product at the top of the shop scroller', async () => {
    const navigate = vi.fn()
    const connectors: MockConnectors = { connections: null, pending: null, error: '', refresh: vi.fn(async () => true), connect: vi.fn(async () => true) }
    const view = render(<ShopClient token="token" connectors={connectors} url={new URL(productUrl(product.shop_key), window.location.origin)} onNavigate={navigate} />)
    await screen.findByRole('link', { name: /Canvas tote/ })
    const page = screen.getByLabelText('Shop page content')
    page.scrollTop = 500
    view.rerender(<ShopClient token="token" connectors={connectors} url={new URL(productUrl(product.shop_key, product.sku), window.location.origin)} onNavigate={navigate} />)
    expect(page.scrollTop).toBe(0)
    await screen.findByRole('region', { name: 'Product details' })
  })
})
