import { useState } from 'react'
import { safeProductImage } from './product-image-url'

export function ProductImage({ url, name }: { url: string | null; name: string }) {
  const source = safeProductImage(url)
  const [failed, setFailed] = useState<string | null>(null)
  return <div className="product-image">
    {source && failed !== source ? <img src={source} alt={name} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(source)} />
      : <div className="product-image-placeholder"><svg viewBox="0 0 48 48" width="48" height="48" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true"><path d="m8 15 16-8 16 8v19l-16 8-16-8V15Zm0 0 16 8 16-8M24 23v19M16 11l16 8v9" /></svg><span>{source ? 'Image unavailable' : 'No product image'}</span></div>}
  </div>
}
