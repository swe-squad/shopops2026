import { useEffect, useState } from 'react'
import { CatalogReadError, readCatalog } from './catalog-api'

// Each mounted browser tab owns its read state. A new scope never displays the previous shop's records.
export function useCatalogRead<T>(path: string | null, kind: 'shops' | 'catalog' | 'product', token: string, active: boolean, reload: number) {
  const [visible, setVisible] = useState(document.visibilityState !== 'hidden')
  const [refresh, setRefresh] = useState(0)
  const [result, setResult] = useState<{ path: string; token: string; data?: T; error: string } | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const current = result?.path === path && result.token === token ? result : null

  useEffect(() => {
    const changed = () => setVisible(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', changed)
    return () => document.removeEventListener('visibilitychange', changed)
  }, [])

  useEffect(() => {
    if (!path || !active || !visible) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function read() {
      setRefreshing(true)
      try {
        const data = await readCatalog<T>(path!, kind, token, controller.signal)
        if (!controller.signal.aborted) setResult({ path: path!, token, data, error: '' })
      } catch (reason) {
        // Cached evidence remains readable only through a temporary source outage, never a revoked grant.
        const preserveData = reason instanceof CatalogReadError && reason.kind === 'transient'
        if (!controller.signal.aborted) setResult(previous => ({ path: path!, token,
          data: preserveData && previous?.path === path && previous.token === token ? previous.data : undefined,
          error: reason instanceof Error ? reason.message : 'Could not refresh product data. Please try again.',
        }))
      } finally {
        if (!controller.signal.aborted) {
          setRefreshing(false)
          timer = setTimeout(() => { void read() }, 2000)
        }
      }
    }
    void read()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [path, kind, token, active, visible, reload, refresh])

  return { data: current?.data, error: current?.error ?? '', loading: !current?.data && !current?.error,
    refreshing, refresh: () => setRefresh(value => value + 1) }
}
