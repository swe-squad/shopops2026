import { useId, useState } from 'react'
import { formatMoney, formatObserved } from './catalog-api'
import type { ProductSnapshot } from './catalog-api'

export function ProductEvidence({ snapshot, draft, onDraftChange }: { snapshot: ProductSnapshot; draft: string; onDraftChange: (value: string) => void }) {
  const [tab, setTab] = useState('reviews')
  const prefix = useId()
  const { product, reviews, orders, returns } = snapshot
  const tabs = [
    { id: 'reviews', label: 'Reviews', count: reviews.length },
    { id: 'orders', label: 'Related orders', count: product.order_count },
    { id: 'returns', label: 'Related returns', count: returns.length },
  ]
  return <>
    <section className="product-evidence" aria-label="Product evidence">
      <div className="evidence-tabs" role="tablist" aria-label="Product evidence views">
        {tabs.map((item, index) => <button key={item.id} id={`${prefix}-${item.id}-tab`} role="tab" aria-selected={tab === item.id} aria-controls={`${prefix}-${item.id}-panel`} tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)} onKeyDown={event => {
          const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1
          if (next < 0) return
          event.preventDefault(); setTab(tabs[next].id)
          document.getElementById(`${prefix}-${tabs[next].id}-tab`)?.focus()
        }}>{item.label} <span>{item.count}</span></button>)}
      </div>
      <div role="tabpanel" id={`${prefix}-reviews-panel`} aria-labelledby={`${prefix}-reviews-tab`} hidden={tab !== 'reviews'} tabIndex={0} className="evidence-panel">
        <h2>Customer reviews</h2>
        {reviews.length ? <ul className="evidence-list">{reviews.map(review => <li key={review.review_id}>
          <div className="evidence-record-top"><strong className="review-rating" aria-label={`${review.rating} out of 5 stars`}>{'★'.repeat(review.rating)}<span aria-hidden="true">{'☆'.repeat(5 - review.rating)}</span> <span>{review.rating}/5</span></strong><time dateTime={review.reviewed_at}>{formatObserved(review.reviewed_at)}</time></div>
          <p>{review.body || 'No written review.'}</p><small>Review {review.review_id} · Order {review.order_id}</small>
        </li>)}</ul> : <p className="evidence-empty">No reviews observed for this product.</p>}
      </div>
      <div role="tabpanel" id={`${prefix}-orders-panel`} aria-labelledby={`${prefix}-orders-tab`} hidden={tab !== 'orders'} tabIndex={0} className="evidence-panel">
        <h2>Related orders</h2><p className="evidence-caption">Observed order lines for this SKU. An order can contain more than one line.</p>
        {orders.length ? <ul className="evidence-list">{orders.map((order, index) => <li key={`${order.order_id}-${index}`}>
          <div className="evidence-record-top"><strong>{order.order_id}</strong><span className="record-status">{order.status}</span></div>
          <p>{order.quantity} × {formatMoney(order.unit_price, product.currency)}</p><small>Ordered {formatObserved(order.ordered_at)}</small>
        </li>)}</ul> : <p className="evidence-empty">No order lines observed for this product.</p>}
      </div>
      <div role="tabpanel" id={`${prefix}-returns-panel`} aria-labelledby={`${prefix}-returns-tab`} hidden={tab !== 'returns'} tabIndex={0} className="evidence-panel">
        <h2>Returns on related orders</h2><p className="evidence-caption">A return on an order containing this product does not confirm that this SKU was returned.</p>
        {returns.length ? <ul className="evidence-list">{returns.map(returned => <li key={returned.return_id}>
          <div className="evidence-record-top"><strong>{returned.return_id}</strong><span className="record-status">{returned.status}</span></div>
          <p>{returned.reason || 'No reason provided.'}</p><p>Refund {formatMoney(returned.refund_amount, product.currency)}</p><small>Order {returned.order_id} · Requested {formatObserved(returned.requested_at)}</small>
        </li>)}</ul> : <p className="evidence-empty">No returns observed on related orders.</p>}
      </div>
    </section>
    <section className="investigation-draft" aria-labelledby={`${prefix}-draft-title`}>
      <div><span className="catalog-eyebrow">INVESTIGATE WITH CONTEXT</span><h2 id={`${prefix}-draft-title`}>Start with a clearer question.</h2><p>Keep a question here, then copy it into your separate agent chat.</p><button type="button" className="secondary-button" onClick={() => onDraftChange(`Investigate ${product.name} (shop ${product.shop_key}, SKU ${product.sku}). Compare its reviews, related orders and returns using source revision ${snapshot.source_revision}. Explain the evidence and uncertainty before suggesting any action.`)}>Prepare question draft</button></div>
      <div className="field"><label htmlFor={`${prefix}-question`}>Investigation question · draft only</label><textarea id={`${prefix}-question`} rows={5} placeholder="What should the agent investigate about this product?" value={draft} onChange={event => onDraftChange(event.target.value)} /><small>This draft stays in this browser tab. It has not been sent and makes no shop changes.</small></div>
    </section>
  </>
}
