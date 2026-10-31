// @vitest-environment node
import { createServer } from 'node:http'
import { afterEach, describe, expect, it } from 'vitest'
import { createConnectorHandler } from './connectors.ts'

const servers: ReturnType<typeof createServer>[] = []
async function start() {
  const server = createServer(createConnectorHandler())
  servers.push(server)
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const address = server.address() as { port: number }
  return `http://127.0.0.1:${address.port}`
}
afterEach(async () => {
  await Promise.all(servers.splice(0).map(server => new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()))))
})

describe('RAM connector API', () => {
  it('shares two independent flags across requests, repeats safely, and resets in a new instance', async () => {
    const origin = await start()
    const endpoint = `${origin}/api/mock/connectors`
    const initial = await fetch(endpoint)
    expect(initial.headers.get('Cache-Control')).toBe('no-store')
    expect(await initial.json()).toEqual({ connections: ['shopee', 'tiktok'].map(platform => ({ platform, connected: false, mock: true })) })
    for (let index = 0; index < 2; index++) {
      const response = await fetch(`${endpoint}/shopee`, { method: 'PUT', headers: { Origin: origin } })
      expect(await response.json()).toEqual({ platform: 'shopee', connected: true, mock: true })
    }
    expect(await (await fetch(endpoint)).json()).toEqual({ connections: [
      { platform: 'shopee', connected: true, mock: true }, { platform: 'tiktok', connected: false, mock: true },
    ] })
    expect((await fetch(`${endpoint}/tiktok`, { method: 'PUT' })).status).toBe(200)
    const fresh = await start()
    expect(await (await fetch(`${fresh}/api/mock/connectors`)).json()).toMatchObject({ connections: [{ connected: false }, { connected: false }] })
  })

  it('rejects unknown platforms, methods, paths and cross-origin writes without changing flags', async () => {
    const origin = await start()
    for (const [path, method, headers, status] of [
      ['/api/mock/connectors/amazon', 'PUT', {}, 400],
      ['/api/mock/connectors', 'POST', {}, 405],
      ['/api/mock/connectors/shopee', 'GET', {}, 405],
      ['/api/mock/unknown', 'GET', {}, 404],
      ['/api/mock/connectors/shopee/extra', 'PUT', {}, 404],
      ['/api/mock/connectors/shopee', 'PUT', { Origin: 'https://other.example' }, 403],
      ['/api/mock/connectors/shopee', 'PUT', { Origin: 'null' }, 403],
    ] as const) {
      const response = await fetch(`${origin}${path}`, { method, headers })
      expect(response.status).toBe(status)
      expect(response.headers.get('access-control-allow-origin')).toBeNull()
    }
    const response = await fetch(`${origin}/api/mock/connectors`)
    expect(await response.json()).toMatchObject({ connections: [{ connected: false }, { connected: false }] })
  })

  it('accepts the HTTPS origin forwarded by nginx behind CapRover', async () => {
    const origin = await start()
    const response = await fetch(`${origin}/api/mock/connectors/shopee`, {
      method: 'PUT', headers: { Origin: origin.replace('http:', 'https:'), 'X-Forwarded-Proto': 'https' },
    })
    expect(response.status).toBe(200)
    expect(await response.json()).toMatchObject({ platform: 'shopee', connected: true })
  })
})
