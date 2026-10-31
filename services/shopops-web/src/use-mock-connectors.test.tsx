import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useMockConnectors } from './use-mock-connectors'

const connection = (platform: string, connected = false) => ({ platform, connected, mock: true })
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

it('reads and updates independent flags through the API without credentials or browser persistence', async () => {
  const fetchMock = vi.fn(async (_url: string, options?: RequestInit) => json(options?.method === 'PUT' ? connection('shopee', true) : { connections: [connection('shopee'), connection('tiktok')] }))
  vi.stubGlobal('fetch', fetchMock)
  const { result } = renderHook(useMockConnectors)
  await act(async () => { await result.current.refresh() })
  await act(async () => { expect(await result.current.connect('shopee')).toBe(true) })
  expect(result.current.connections).toEqual([connection('shopee', true), connection('tiktok')])
  expect(fetchMock).toHaveBeenLastCalledWith('/api/mock/connectors/shopee', expect.objectContaining({ method: 'PUT', credentials: 'omit' }))
  expect(fetchMock.mock.calls.every(([, options]) => !options?.headers)).toBe(true)
  expect(localStorage.length).toBe(0)
  expect(sessionStorage.length).toBe(0)
})

it('does not claim success on HTTP errors or malformed responses and allows retry', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json({}, 500)).mockResolvedValueOnce(json({ connections: [connection('shopee'), connection('tiktok')] })).mockResolvedValueOnce(json(connection('tiktok', true))))
  const { result } = renderHook(useMockConnectors)
  await act(async () => { expect(await result.current.refresh()).toBe(false) })
  expect(result.current.error).toMatch(/Could not check/)
  await act(async () => { await result.current.refresh() })
  expect(result.current.error).toBe('')
  await act(async () => { expect(await result.current.connect('shopee')).toBe(false) })
  expect(result.current.connections?.every(item => !item.connected)).toBe(true)
  expect(result.current.error).toMatch(/Could not save/)
})

it('aborts requests on unmount and ignores a response from a replaced request', async () => {
  let resolveOld!: (value: Response) => void
  const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { resolveOld = resolve })).mockResolvedValue(json({ connections: [connection('shopee'), connection('tiktok')] }))
  vi.stubGlobal('fetch', fetchMock)
  const { result, unmount } = renderHook(useMockConnectors)
  let old!: Promise<boolean>
  act(() => { old = result.current.refresh() })
  const signal = fetchMock.mock.calls[0][1].signal as AbortSignal
  await act(async () => { await result.current.refresh() })
  expect(signal.aborted).toBe(true)
  await act(async () => { resolveOld(json({ connections: [connection('shopee', true), connection('tiktok', true)] })); expect(await old).toBe(false) })
  expect(result.current.connections?.every(item => !item.connected)).toBe(true)
  fetchMock.mockImplementation(() => new Promise(() => {}))
  act(() => { void result.current.refresh() })
  const pendingSignal = fetchMock.mock.calls[2][1].signal as AbortSignal
  unmount()
  expect(pendingSignal.aborted).toBe(true)
})

it('times out a stalled request and leaves the UI retryable', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn((_url: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
    options.signal!.addEventListener('abort', () => reject(new Error('aborted')), { once: true })
  })))
  const { result } = renderHook(useMockConnectors)
  let pending!: Promise<boolean>
  act(() => { pending = result.current.refresh() })
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000); expect(await pending).toBe(false) })
  expect(result.current.pending).toBeNull()
  expect(result.current.error).toMatch(/Could not check/)
})
