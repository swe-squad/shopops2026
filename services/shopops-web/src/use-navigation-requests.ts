import { useEffect, useState } from 'react'
import { authHeaders, checkResponse } from './workspace-api'

type NavigationRequest = { id: number; url: string }

export function useNavigationRequests(token: string) {
  const [request, setRequest] = useState<{ url: string; sequence: number } | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let latestId: number | null = null

    async function poll() {
      try {
        const response = await fetch('/api/operations/navigation', { headers: authHeaders(token), signal: controller.signal, cache: 'no-store' })
        await checkResponse(response, 'Could not receive links from chat')
        const navigation = await response.json() as NavigationRequest | null
        if (controller.signal.aborted) return
        if (navigation && typeof navigation.id === 'number' && typeof navigation.url === 'string' && navigation.id > (latestId ?? 0)) {
          // The first snapshot is history, not a new request to replace the login destination.
          if (latestId !== null) setRequest({ url: navigation.url, sequence: navigation.id })
          latestId = navigation.id
        }
        latestId ??= 0
        setError('')
      } catch {
        if (!controller.signal.aborted) setError('Could not receive links from chat. Reconnecting…')
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(() => { void poll() }, 1000)
      }
    }

    void poll()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [token])

  return { request, error }
}
