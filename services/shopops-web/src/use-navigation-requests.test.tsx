import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useNavigationRequests } from './use-navigation-requests'

beforeEach(() => { vi.useFakeTimers(); window.history.replaceState(null, '', '/') })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/') })

describe('navigation mailbox on entry', () => {
  it('preserves an explicit product entry and follows later chat navigation', async () => {
    window.history.replaceState(null, '', '/shop/products?shop_key=demo&sku=SHIRT-M')
    let navigation = { id: 7, url: '/shop/overview' }
    vi.stubGlobal('fetch', vi.fn(async () => Response.json(navigation)))
    const { result } = renderHook(() => useNavigationRequests('test-workspace'))
    await act(async () => {})
    expect(result.current.request).toBeNull()
    navigation = { id: 8, url: '/shop/incidents' }
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(result.current.request).toEqual({ sequence: 8, url: '/shop/incidents' })
  })

  it('continues to open the latest mailbox target for the ordinary app entry', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ id: 7, url: '/shop/products?shop_key=demo&sku=SHIRT-M' })))
    const { result } = renderHook(() => useNavigationRequests('test-workspace'))
    await act(async () => {})
    expect(result.current.request).toEqual({ sequence: 7, url: '/shop/products?shop_key=demo&sku=SHIRT-M' })
  })
})
