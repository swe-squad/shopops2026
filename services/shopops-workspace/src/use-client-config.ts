import { useEffect, useState } from 'react'
import { validateClientConfig } from './client-config'
import type { ClientConfig } from './client-config'

export function useClientConfig() {
  const [config, setConfig] = useState<ClientConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    void (async () => {
      try {
        const response = await fetch('/client-config.json', { headers: { Accept: 'application/json' }, credentials: 'omit', cache: 'no-store', signal: controller.signal })
        if (!response.ok) throw new Error('Could not load the client app configuration. Please try again.')
        const next = validateClientConfig(await response.json())
        if (!controller.signal.aborted) setConfig(next)
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not load the client apps.')
      } finally { if (!controller.signal.aborted) setLoading(false) }
    })()
    return () => controller.abort()
  }, [revision])

  function retry() { setConfig(null); setError(''); setLoading(true); setRevision(value => value + 1) }
  return { config, loading, error, retry }
}
