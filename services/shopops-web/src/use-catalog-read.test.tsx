import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCatalogRead } from './use-catalog-read'
import type { CatalogSnapshot } from './catalog-api'
import { catalog, json } from './test/catalog-fixtures'

beforeEach(() => vi.useFakeTimers())
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
const flush = () => act(async () => {})

describe('visible catalog polling', () => {
  it('refreshes observed stock, preserves last good data after errors, and retries successfully', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(catalog)).mockResolvedValueOnce(new Response('', { status: 503 }))
      .mockResolvedValueOnce(json({ ...catalog, source_revision: 2, products: [{ ...catalog.products[0], available: 13 }] }))
    vi.stubGlobal('fetch', fetchMock)
    const { result, unmount } = renderHook(() => useCatalogRead<CatalogSnapshot>('/api/operations/catalog?shop_key=shop%2Fa', 'catalog', 'private-token', true, 0))
    await flush()
    expect(result.current.data?.products[0].available).toBe(2)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(result.current.data?.products[0].available).toBe(2)
    expect(result.current.error).toContain('unavailable')
    await act(async () => { result.current.refresh() })
    await flush()
    expect(result.current.data?.products[0].available).toBe(13)
    expect(result.current.data?.source_revision).toBe(2)
    expect(result.current.error).toBe('')
    expect(fetchMock).toHaveBeenCalledWith('/api/operations/catalog?shop_key=shop%2Fa', expect.objectContaining({ headers: { Authorization: 'Bearer private-token' }, cache: 'no-store' }))
    unmount()
    expect(fetchMock.mock.calls.every(([, options]) => (options.signal as AbortSignal).aborted)).toBe(true)
  })

  it('pauses inactive tabs and hidden documents, resuming with a fresh read', async () => {
    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    const fetchMock = vi.fn(async () => json(catalog))
    vi.stubGlobal('fetch', fetchMock)
    const { rerender } = renderHook(({ active }) => useCatalogRead<CatalogSnapshot>('/catalog', 'catalog', 'token', active, 0), { initialProps: { active: false } })
    await flush()
    expect(fetchMock).not.toHaveBeenCalled()
    rerender({ active: true }); await flush()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    visibility.mockReturnValue('hidden')
    act(() => document.dispatchEvent(new Event('visibilitychange')))
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    visibility.mockReturnValue('visible')
    act(() => document.dispatchEvent(new Event('visibilitychange'))); await flush()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    rerender({ active: false })
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('never exposes another scope or token’s cached records, including after a failed read', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(catalog)).mockResolvedValueOnce(new Response('', { status: 404 })).mockResolvedValueOnce(new Response('', { status: 503 })))
    const { result, rerender } = renderHook(({ path, token }) => useCatalogRead<CatalogSnapshot>(path, 'catalog', token, true, 0), { initialProps: { path: '/catalog?a', token: 'one' } })
    await flush(); expect(result.current.data).toBeDefined()
    rerender({ path: '/catalog?b', token: 'one' })
    expect(result.current.data).toBeUndefined()
    await flush(); expect(result.current.error).toContain('unavailable')
    rerender({ path: '/catalog?a', token: 'two' }); await flush()
    expect(result.current.data).toBeUndefined()
  })

  it('rejects malformed source records instead of inventing products', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ ...catalog, products: [{ ...catalog.products[0], available: '13' }] })))
    const { result } = renderHook(() => useCatalogRead<CatalogSnapshot>('/catalog', 'catalog', 'token', true, 0))
    await flush()
    expect(result.current.data).toBeUndefined()
    expect(result.current.error).toContain('could not be read')
  })

  it.each([403, 404, 422])('clears previously successful evidence when the selection becomes unavailable (%s)', async status => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(catalog)).mockResolvedValueOnce(new Response('', { status })))
    const { result } = renderHook(() => useCatalogRead<CatalogSnapshot>('/catalog', 'catalog', 'token', true, 0))
    await flush()
    expect(result.current.data).toEqual(catalog)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(result.current.data).toBeUndefined()
    expect(result.current.error).not.toBe('')
  })

  it('clears cached evidence when the current token is rejected, even if the next retry is a source outage', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(catalog)).mockResolvedValueOnce(new Response('', { status: 401 })).mockResolvedValueOnce(new Response('', { status: 503 })))
    const { result } = renderHook(() => useCatalogRead<CatalogSnapshot>('/catalog', 'catalog', 'expired-token', true, 0))
    await flush()
    expect(result.current.data).toEqual(catalog)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(result.current.data).toBeUndefined()
    expect(result.current.error).toContain('Workspace token is not valid')
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(result.current.data).toBeUndefined()
  })

  it('retains last good records during a network outage', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(catalog)).mockRejectedValueOnce(new TypeError('Failed to fetch')))
    const { result } = renderHook(() => useCatalogRead<CatalogSnapshot>('/catalog', 'catalog', 'token', true, 0))
    await flush()
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(result.current.data).toEqual(catalog)
    expect(result.current.error).toContain('Could not reach the product source')
  })

  it('clears cached evidence when a refresh no longer satisfies the catalog contract', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(catalog)).mockResolvedValueOnce(json({ ...catalog, products: [{}] })))
    const { result } = renderHook(() => useCatalogRead<CatalogSnapshot>('/catalog', 'catalog', 'token', true, 0))
    await flush()
    expect(result.current.data).toEqual(catalog)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(result.current.data).toBeUndefined()
    expect(result.current.error).toContain('could not be read')
  })
})
