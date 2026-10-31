import { authHeaders } from './workspace-api'

export type Shop = { shop_key: string; name: string; platform: string; currency: string; timezone: string }
export type Product = {
  shop_key: string; sku: string; name: string; image_url: string | null; unit_cost: string | null; currency: string
  available: number | null; inventory_observed_at: string | null; last_sold_price: string | null; last_sold_at: string | null
  order_count: number; review_count: number; negative_review_count: number; return_order_count: number
}
export type Review = { review_id: string; order_id: string; reviewed_at: string; rating: number; body: string }
export type Order = { order_id: string; ordered_at: string; status: string; quantity: number; unit_price: string }
export type Return = { return_id: string; order_id: string; requested_at: string; reason: string; status: string; refund_amount: string }
type Freshness = { source_revision: number; fetched_at: string }
export type ShopList = Freshness & { shops: Shop[] }
export type CatalogSnapshot = Freshness & { shop: Shop; products: Product[]; data_mode: 'mock_source' }
export type ProductSnapshot = Freshness & { shop: Shop; product: Product; reviews: Review[]; orders: Order[]; returns: Return[]; data_mode: 'mock_source' }

export type CatalogErrorKind = 'transient' | 'unauthorized' | 'forbidden' | 'not_found' | 'invalid_selection' | 'invalid_response' | 'request'

export class CatalogReadError extends Error {
  readonly kind: CatalogErrorKind
  readonly status?: number

  constructor(message: string, kind: CatalogErrorKind, status?: number) {
    super(message)
    this.name = 'CatalogReadError'
    this.kind = kind
    this.status = status
  }
}

const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const strings = (value: Record<string, unknown>, keys: string[]) => keys.every(key => typeof value[key] === 'string')
const date = (value: unknown) => typeof value === 'string' && !Number.isNaN(Date.parse(value))
const money = (value: unknown) => typeof value === 'string' && /^-?\d+(?:\.\d+)?$/.test(value) && Number.isFinite(Number(value))
const count = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
const nullable = (value: unknown, validate: (item: unknown) => boolean) => value === null || validate(value)
const list = (value: unknown, validate: (item: unknown) => boolean) => Array.isArray(value) && value.every(validate)
const shop = (value: unknown) => record(value) && strings(value, ['shop_key', 'name', 'platform', 'currency', 'timezone'])
const product = (value: unknown) => record(value) && strings(value, ['shop_key', 'sku', 'name', 'currency'])
  && nullable(value.image_url, item => typeof item === 'string') && nullable(value.unit_cost, money)
  && nullable(value.available, count) && nullable(value.inventory_observed_at, date)
  && nullable(value.last_sold_price, money) && nullable(value.last_sold_at, date)
  && ['order_count', 'review_count', 'negative_review_count', 'return_order_count'].every(key => count(value[key]))
const review = (value: unknown) => record(value) && strings(value, ['review_id', 'order_id', 'body']) && date(value.reviewed_at)
  && typeof value.rating === 'number' && Number.isInteger(value.rating) && value.rating >= 1 && value.rating <= 5
const order = (value: unknown) => record(value) && strings(value, ['order_id', 'status']) && date(value.ordered_at) && count(value.quantity) && money(value.unit_price)
const returned = (value: unknown) => record(value) && strings(value, ['return_id', 'order_id', 'reason', 'status']) && date(value.requested_at) && money(value.refund_amount)

function validResponse(value: unknown, kind: 'shops' | 'catalog' | 'product') {
  if (!record(value) || !count(value.source_revision) || !date(value.fetched_at)) return false
  if (kind === 'shops') return list(value.shops, shop)
  if (!shop(value.shop) || value.data_mode !== 'mock_source') return false
  if (kind === 'catalog') return list(value.products, product)
  return product(value.product)
    && list(value.reviews, review)
    && list(value.orders, order)
    && list(value.returns, returned)
}

export async function readCatalog<T>(path: string, kind: 'shops' | 'catalog' | 'product', token: string, signal: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { headers: authHeaders(token), signal, cache: 'no-store' })
  } catch (reason) {
    if (signal.aborted) throw reason
    throw new CatalogReadError('Could not reach the product source. Please try again.', 'transient')
  }
  if (response.status === 401) throw new CatalogReadError('Workspace token is not valid. Lock the workspace and try again.', 'unauthorized', 401)
  if (response.status === 403) throw new CatalogReadError('This workspace no longer has access to this shop or product. Choose another selection.', 'forbidden', 403)
  if (response.status === 404) throw new CatalogReadError('This shop or product is unavailable for this workspace. Choose another selection.', 'not_found', 404)
  if (response.status === 400 || response.status === 422) throw new CatalogReadError('This product selection is not valid. Choose another shop or product.', 'invalid_selection', response.status)
  if (response.status === 503) throw new CatalogReadError('Product data is unavailable. The source may be disconnected or refreshing. Try again shortly.', 'transient', 503)
  if (response.status >= 500) throw new CatalogReadError(`Could not load product data (${response.status}). Please try again.`, 'transient', response.status)
  if (!response.ok) throw new CatalogReadError(`Could not load product data (${response.status}). Please try again.`, 'request', response.status)
  let data: unknown
  try { data = await response.json() }
  catch { throw new CatalogReadError('The product response could not be read. Please try again.', 'invalid_response') }
  if (!validResponse(data, kind)) throw new CatalogReadError('The product response could not be read. Please try again.', 'invalid_response')
  return data as T
}

export function productUrl(shopKey: string, sku?: string) {
  const query = new URLSearchParams({ shop_key: shopKey })
  if (sku) query.set('sku', sku)
  return `/shop/products?${query}`
}

export function formatMoney(value: string | null, currency: string) {
  if (value === null) return 'Not observed'
  try { return new Intl.NumberFormat('en', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value)) }
  catch { return `${value} ${currency}` }
}

export function formatObserved(value: string | null) {
  return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Not observed'
}
