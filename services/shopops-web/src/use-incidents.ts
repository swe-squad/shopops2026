import { useEffect, useRef, useState } from 'react'
import { authHeaders, checkResponse, parseIncidentTime } from './workspace-api'
import type { Incident } from './workspace-api'

function isIncident(value: unknown): value is Incident {
  if (!value || typeof value !== 'object') return false
  const record = value as Partial<Incident>
  return typeof record.id === 'number' && Number.isInteger(record.id) && record.id > 0
    && typeof record.title === 'string' && typeof record.detail === 'string'
    && typeof record.created_at === 'string' && !Number.isNaN(parseIncidentTime(record.created_at).getTime())
}

export function useIncidents(token: string, reload: number) {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [loadResult, setLoadResult] = useState<{ token: string; reload: number; refresh: number; error: string } | null>(null)
  const saveController = useRef<AbortController | null>(null)
  const mutationVersion = useRef(0)
  const loading = !loadResult || loadResult.token !== token || loadResult.reload !== reload || loadResult.refresh !== refresh

  useEffect(() => {
    const controller = new AbortController()
    const version = mutationVersion.current
    void (async () => {
      let error = ''
      try {
        const response = await fetch('/api/operations/incidents', { headers: authHeaders(token), signal: controller.signal, cache: 'no-store' })
        await checkResponse(response, 'Could not load incidents')
        const data: unknown = await response.json()
        if (!Array.isArray(data) || !data.every(isIncident)) throw new Error('The incident response could not be read. Please try again.')
        // A read started before a save must not erase the newly created record.
        if (!controller.signal.aborted && version === mutationVersion.current) setIncidents(data)
      } catch (reason) {
        error = reason instanceof Error ? reason.message : 'Could not load incidents. Please try again.'
      } finally {
        if (!controller.signal.aborted) setLoadResult({ token, reload, refresh, error })
      }
    })()
    return () => controller.abort()
  }, [token, refresh, reload])

  useEffect(() => () => { saveController.current?.abort(); saveController.current = null }, [])

  async function addIncident(title: string, detail: string) {
    if (!title.trim() || saveController.current) return false
    const controller = new AbortController()
    saveController.current = controller
    setSaving(true)
    setSaveError('')
    try {
      const response = await fetch('/api/operations/incidents', {
        method: 'POST', headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), detail: detail.trim() }), signal: controller.signal,
      })
      await checkResponse(response, 'Could not add the incident')
      const incident: unknown = await response.json()
      if (!isIncident(incident)) throw new Error('The save response could not be read. Refresh incidents before trying again.')
      if (controller.signal.aborted) return false
      mutationVersion.current += 1
      setIncidents(items => [incident, ...items.filter(item => item.id !== incident.id)].slice(0, 100))
      return true
    } catch (reason) {
      if (!controller.signal.aborted) setSaveError(reason instanceof Error ? reason.message : 'Could not add the incident. Please try again.')
      return false
    } finally {
      if (saveController.current === controller) { saveController.current = null; setSaving(false) }
    }
  }

  return { incidents, loading, saving, loadError: loading ? '' : loadResult.error, saveError, addIncident, refresh: () => setRefresh(value => value + 1) }
}
