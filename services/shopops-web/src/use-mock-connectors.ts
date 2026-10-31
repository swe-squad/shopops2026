import { useCallback, useEffect, useRef, useState } from 'react'

export const platforms = { shopee: 'Shopee', tiktok: 'TikTok' } as const
export type Platform = keyof typeof platforms
type Connection = { platform: Platform; connected: boolean; mock: true }
type State = { connections: Connection[] | null; pending: 'checking' | Platform | null; error: string }

function isConnection(value: unknown): value is Connection {
  if (!value || typeof value !== 'object') return false
  const item = value as Partial<Connection>
  return (item.platform === 'shopee' || item.platform === 'tiktok') && typeof item.connected === 'boolean' && item.mock === true
}

export function useMockConnectors() {
  const [state, setState] = useState<State>({ connections: null, pending: null, error: '' })
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => { request.current?.abort(); request.current = null }, [])

  const run = useCallback(async (platform?: Platform) => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setState(previous => ({ connections: platform ? previous.connections : null, pending: platform ?? 'checking', error: '' }))
    const timeout = setTimeout(() => controller.abort(), 10_000)
    try {
      const response = await fetch(`/api/mock/connectors${platform ? `/${platform}` : ''}`, {
        method: platform ? 'PUT' : 'GET', credentials: 'omit', signal: controller.signal,
      })
      if (!response.ok) throw new Error('Mock connection request failed.')
      const body: unknown = await response.json()
      let connections: Connection[]
      if (platform) {
        if (!isConnection(body) || body.platform !== platform || !body.connected) throw new Error('Invalid mock connection response.')
        connections = [body]
      } else {
        const items = (body as { connections?: unknown } | null)?.connections
        if (!Array.isArray(items) || items.length !== 2 || !items.every(isConnection) || !Object.keys(platforms).every(key => items.some(item => item.platform === key))) {
          throw new Error('Invalid mock connections response.')
        }
        connections = items
      }
      if (request.current !== controller) return false
      if (controller.signal.aborted) throw new Error('Mock connection request timed out.')
      setState(previous => ({
        connections: platform ? previous.connections?.map(item => item.platform === platform ? connections[0] : item) ?? null : connections,
        pending: null, error: '',
      }))
      return true
    } catch {
      if (request.current === controller) setState(previous => ({ ...previous, pending: null, error: platform ? 'Could not save the demo connection. Check the status or try again.' : 'Could not check demo connections. Please try again.' }))
      return false
    } finally {
      clearTimeout(timeout)
      if (request.current === controller) request.current = null
    }
  }, [])

  const refresh = useCallback(() => run(), [run])
  const connect = useCallback((platform: Platform) => run(platform), [run])
  return { ...state, refresh, connect }
}

export type MockConnectors = ReturnType<typeof useMockConnectors>
