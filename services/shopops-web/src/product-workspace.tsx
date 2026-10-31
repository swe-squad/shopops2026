import { useId, useState } from 'react'
import { BrowserIcon } from './browser-icon'
import { formatMoney, formatObserved, productUrl } from './catalog-api'
import type { CatalogSnapshot, Product, ProductSnapshot, ShopList } from './catalog-api'
import { ProductEvidence } from './product-evidence'
import { ProductImage } from './product-image'
import { useCatalogRead } from './use-catalog-read'
import './product-workspace.css'

function ProductTile({ product, onNavigate }: { product: Product; onNavigate: (path: string) => void }) {
  const path = productUrl(product.shop_key, product.sku)
  return <a className="product-tile" href={path} onClick={event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    event.preventDefault(); onNavigate(path)
  }}>
    <ProductImage url={product.image_url} name={product.name} />
    <div className="product-tile-content"><span className="product-sku">{product.sku}</span><h2>{product.name}</h2>
      <span className="sale-caption">Last observed sale</span><strong className="product-price">{formatMoney(product.last_sold_price, product.currency)}</strong>
      <div className="product-tile-meta"><span>{product.available === null ? 'Stock unknown' : `${product.available} in observed stock`}</span><span>{product.order_count} orders</span></div>
      <div className="product-tile-foot"><span>{product.review_count} reviews</span>{product.negative_review_count > 0 && <span className="product-attention">{product.negative_review_count} low-rated</span>}</div>
    </div>
  </a>
}

export function ProductWorkspace({ token, url, active, reload, onNavigate }: { token: string; url: URL; active: boolean; reload: number; onNavigate: (path: string) => void }) {
  const prefix = useId()
  const [search, setSearch] = useState('')
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const shops = useCatalogRead<ShopList>('/api/operations/catalog/shops', 'shops', token, active, reload)
  const shopKey = url.searchParams.get('shop_key') ?? shops.data?.shops[0]?.shop_key ?? ''
  const sku = url.searchParams.get('sku') ?? ''
  const draftScope = JSON.stringify([shopKey, sku])
  const query = new URLSearchParams({ shop_key: shopKey })
  if (sku) query.set('sku', sku)
  const catalog = useCatalogRead<CatalogSnapshot>(shopKey ? `/api/operations/catalog?${new URLSearchParams({ shop_key: shopKey })}` : null, 'catalog', token, active && !sku, reload)
  const detail = useCatalogRead<ProductSnapshot>(shopKey && sku ? `/api/operations/catalog/product?${query}` : null, 'product', token, active && !!sku, reload)
  const selected = sku ? detail : catalog
  const snapshot = selected.data
  const error = selected.error || shops.error
  const products = catalog.data?.products.filter(product => `${product.name} ${product.sku}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) ?? []
  const refresh = () => { shops.refresh(); selected.refresh() }
  const currentShop = snapshot?.shop ?? shops.data?.shops.find(shop => shop.shop_key === shopKey)
  return <div className="product-workspace">
    <header className="catalog-header">
      <div className="catalog-heading"><span className="catalog-eyebrow">YOUR SHOP, IN FOCUS</span><h1>Products</h1><p>Explore your catalog. Follow the evidence.</p></div>
      <div className="catalog-shop-field"><label htmlFor={`${prefix}-shop`}>Shop</label><select id={`${prefix}-shop`} value={shopKey} disabled={!shops.data?.shops.length} onChange={event => { setSearch(''); onNavigate(productUrl(event.target.value)) }}>
        {!shops.data?.shops.length && <option value="">{shops.loading ? 'Loading shops…' : 'No shops available'}</option>}
        {shopKey && !shops.data?.shops.some(shop => shop.shop_key === shopKey) && <option value={shopKey}>{shopKey}</option>}
        {shops.data?.shops.map(shop => <option key={shop.shop_key} value={shop.shop_key}>{shop.name}</option>)}
      </select></div>
    </header>
    <div className="catalog-body">
      <div className="catalog-context"><div><strong>{currentShop?.name ?? 'Shop catalog'}</strong><span>{currentShop?.platform ?? 'Commerce'} · Inspection only</span></div><span className="catalog-source">Persistent mock source</span></div>
      {error && <div className="catalog-notice" role="status"><div><strong>{snapshot ? 'Showing last good data · refresh failed' : 'Product data unavailable'}</strong><p>{error}</p></div><button type="button" className="secondary-button" onClick={refresh}>Retry</button></div>}
      {snapshot && <div className="catalog-freshness"><span>Source revision {snapshot.source_revision} · Fetched {formatObserved(snapshot.fetched_at)}</span><span>{selected.refreshing ? 'Refreshing…' : active ? 'Auto-refresh every 2 seconds' : 'Refresh paused'}</span></div>}
      {!snapshot && !error && (shops.loading || (!!shopKey && selected.loading)) && <div className="catalog-loading" role="status"><strong>Loading your {sku ? 'product evidence' : 'products'}…</strong><p>Reading the connected source.</p><div className="catalog-skeleton" aria-hidden="true">{[0, 1, 2, 3].map(item => <span key={item} />)}</div></div>}
      {!shops.loading && shops.data?.shops.length === 0 && <div className="catalog-empty"><h2>No shops available</h2><p>No shop catalog is available to this workspace.</p><button className="secondary-button" onClick={refresh}>Refresh shops</button></div>}
      {!sku && catalog.data && <>
        <div className="catalog-tools"><div className="catalog-search"><label className="sr-only" htmlFor={`${prefix}-search`}>Search products by name or SKU</label><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="10" cy="10" r="6" /><path d="m15 15 5 5" /></svg><input id={`${prefix}-search`} type="search" placeholder="Search by product name or SKU" value={search} onChange={event => setSearch(event.target.value)} /></div><button type="button" className="secondary-button" onClick={refresh}><BrowserIcon name="reload" />Refresh</button></div>
        <div className="catalog-results"><h2>All products <span>{products.length}</span></h2><p>Prices and stock reflect observed records.</p></div>
        {products.length ? <div className="product-grid">{products.map(product => <ProductTile key={product.sku} product={product} onNavigate={onNavigate} />)}</div> : <div className="catalog-empty"><h2>{search ? 'No matching products' : 'No products observed'}</h2><p>{search ? `No products match “${search}”. Try a name or SKU.` : 'Products will appear when the source includes catalog records.'}</p>{search && <button className="secondary-button" onClick={() => setSearch('')}>Clear search</button>}</div>}
      </>}
      {sku && detail.data && <>
        <div className="product-breadcrumb"><a href={productUrl(shopKey)} onClick={event => { event.preventDefault(); onNavigate(productUrl(shopKey)) }}>All products</a><span aria-hidden="true">/</span><span>{detail.data.product.sku}</span><button className="text-button" onClick={refresh}><BrowserIcon name="reload" />Refresh</button></div>
        <ProductSummary product={detail.data.product} />
        <ProductEvidence snapshot={detail.data} draft={drafts[draftScope] ?? ''} onDraftChange={value => setDrafts(previous => ({ ...previous, [draftScope]: value }))} />
      </>}
    </div>
  </div>
}

function ProductSummary({ product }: { product: Product }) {
  return <section className="product-summary" aria-label="Product details">
    <ProductImage url={product.image_url} name={product.name} />
    <div className="product-summary-copy"><span className="product-sku">SKU · {product.sku}</span><h2>{product.name}</h2>
      <div className="product-summary-counts"><span><strong>{product.review_count}</strong> reviews</span><span><strong>{product.order_count}</strong> orders</span><span><strong>{product.return_order_count}</strong> orders with returns</span></div>
      <div className="product-price-block"><span>Last observed sale price</span><strong>{formatMoney(product.last_sold_price, product.currency)}</strong><small>{product.last_sold_at ? `Sold ${formatObserved(product.last_sold_at)}` : 'No sale price observed'} · Not a current listing price</small></div>
      <dl className="product-facts"><div><dt>Observed available stock</dt><dd>{product.available ?? 'Unknown'}</dd></div><div><dt>Inventory observed</dt><dd>{formatObserved(product.inventory_observed_at)}</dd></div><div><dt>Unit cost</dt><dd>{formatMoney(product.unit_cost, product.currency)}</dd></div><div><dt>Low-rated reviews</dt><dd>{product.negative_review_count}</dd></div></dl>
    </div>
  </section>
}
