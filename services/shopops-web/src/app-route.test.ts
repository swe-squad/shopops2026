import { describe, expect, it } from 'vitest'
import { defaultShopPath, shopDestination } from './app-route'

describe('login return destination', () => {
  it.each(['/shop', '/shop/overview', '/shop/incidents?filter=open#incident-7', '/shop/incidents?search=late%20shipment#incident-7'])('keeps the local shop destination %s', path => {
    expect(shopDestination(path)).toBe(path)
  })
  it.each([null, '', '/login', '/shopper', 'https://evil.test/shop', '//evil.test/shop', '/\\evil.test/shop', '/shop/../../login', '/shop/../..//evil.test', 'javascript:alert(1)', '/shop/\nincidents', '/shop/%0a', '/shop/%5c', '/%2fevil.test/shop', '/shop/%zz'])('rejects unsafe or non-shop destination %s', path => {
    expect(shopDestination(path)).toBe(defaultShopPath)
  })
})
