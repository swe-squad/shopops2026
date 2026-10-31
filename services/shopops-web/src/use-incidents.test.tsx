import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useIncidents } from './use-incidents'

const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
const incident = { id: 7, title: 'Carrier handoff', detail: 'Review the pickup.', created_at: '2026-10-31T09:00:00Z' }

function deferredResponse() {
  let resolve!: (response: Response) => void
  const promise = new Promise<Response>(complete => { resolve = complete })
  return { promise, resolve }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('incident requests', () => {
  it('reports invalid responses and recovers after an explicit refresh', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json([{ ...incident, created_at: 'not-a-date' }]))
      .mockResolvedValueOnce(json([incident]))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useIncidents('workspace-secret', 0))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.loadError).toBe('The incident response could not be read. Please try again.')
    expect(result.current.incidents).toEqual([])
    act(() => result.current.refresh())
    expect(result.current.loading).toBe(true)
    expect(result.current.loadError).toBe('')
    await waitFor(() => expect(result.current.incidents).toEqual([incident]))
    expect(result.current.loadError).toBe('')
  })

  it('does not erase a completed save when an older read finishes later', async () => {
    const read = deferredResponse()
    vi.stubGlobal('fetch', vi.fn((_url: string, options?: RequestInit) => options?.method === 'POST' ? Promise.resolve(json(incident)) : read.promise))
    const { result } = renderHook(() => useIncidents('workspace-secret', 0))
    await act(async () => { expect(await result.current.addIncident(incident.title, incident.detail)).toBe(true) })
    expect(result.current.incidents).toEqual([incident])
    await act(async () => { read.resolve(json([])) })
    expect(result.current.incidents).toEqual([incident])
    expect(result.current.loading).toBe(false)
  })

  it('prevents duplicate saves and preserves the failure for a deliberate retry', async () => {
    const save = deferredResponse()
    const fetchMock = vi.fn((_url: string, options?: RequestInit) => options?.method === 'POST' ? save.promise : Promise.resolve(json([])))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useIncidents('workspace-secret', 0))
    await waitFor(() => expect(result.current.loading).toBe(false))
    let firstSave!: Promise<boolean>
    act(() => { firstSave = result.current.addIncident(` ${incident.title} `, ` ${incident.detail} `) })
    await act(async () => { expect(await result.current.addIncident(incident.title, incident.detail)).toBe(false) })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenLastCalledWith('/api/operations/incidents', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ title: incident.title, detail: incident.detail }),
      headers: { Authorization: 'Bearer workspace-secret', 'Content-Type': 'application/json' },
    }))
    await act(async () => { save.resolve(new Response('', { status: 500 })); expect(await firstSave).toBe(false) })
    expect(result.current.saveError).toBe('Could not add the incident (500). Please try again.')
    expect(result.current.saving).toBe(false)
    expect(result.current.incidents).toEqual([])
  })

  it('aborts pending reads and saves when its tab closes', async () => {
    const read = deferredResponse()
    const save = deferredResponse()
    const fetchMock = vi.fn((_url: string, options?: RequestInit) => options?.method === 'POST' ? save.promise : read.promise)
    vi.stubGlobal('fetch', fetchMock)
    const { result, unmount } = renderHook(() => useIncidents('workspace-secret', 0))
    let saving!: Promise<boolean>
    act(() => { saving = result.current.addIncident(incident.title, incident.detail) })
    const signals = fetchMock.mock.calls.map(([, options]) => options?.signal as AbortSignal)
    unmount()
    expect(signals).toHaveLength(2)
    expect(signals.every(signal => signal.aborted)).toBe(true)
    await act(async () => {
      read.resolve(json([]))
      save.resolve(json(incident))
      expect(await saving).toBe(false)
    })
  })
})
