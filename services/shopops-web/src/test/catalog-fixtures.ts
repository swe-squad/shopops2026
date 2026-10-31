import type { CatalogSnapshot, ProductSnapshot, ShopList } from '../catalog-api'

export const shop = { shop_key: 'shop/a', name: 'Merchant One', platform: 'Shopee', currency: 'VND', timezone: 'Asia/Ho_Chi_Minh' }
export const product = { shop_key: shop.shop_key, sku: 'SKU/A 1', name: 'Canvas tote', image_url: null, unit_cost: '55000', currency: 'VND', available: 2,
  inventory_observed_at: '2026-10-31T08:00:00Z', last_sold_price: '99000', last_sold_at: '2026-10-31T09:00:00Z', order_count: 1, review_count: 1, negative_review_count: 1, return_order_count: 1 }
const freshness = { source_revision: 1, fetched_at: '2026-10-31T10:00:00Z' }
export const shops: ShopList = { shops: [shop, { ...shop, shop_key: 'other', name: 'Merchant Two' }], ...freshness }
export const catalog: CatalogSnapshot = { shop, products: [product], ...freshness, data_mode: 'mock_source' }
export const detail: ProductSnapshot = { shop, product, ...freshness, data_mode: 'mock_source',
  reviews: [{ review_id: 'review-1', order_id: 'order-1', reviewed_at: '2026-10-31T09:00:00Z', rating: 2, body: 'Seam came loose.' }],
  orders: [{ order_id: 'order-1', ordered_at: '2026-10-31T08:00:00Z', status: 'completed', quantity: 1, unit_price: '99000' }],
  returns: [{ return_id: 'return-1', order_id: 'order-1', requested_at: '2026-10-31T10:00:00Z', status: 'requested', reason: 'Damaged seam', refund_amount: '99000' }],
}
export const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
