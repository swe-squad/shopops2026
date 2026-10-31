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
  it('shares three independent flags across requests, repeats safely, and resets in a new instance', async () => {
    const origin = await start()
    const endpoint = `${origin}/api/mock/connectors`
    const initial = await fetch(endpoint)
    expect(initial.headers.get('Cache-Control')).toBe('no-store')
    expect(await initial.json()).toEqual({ connections: ['shopee', 'shopify', 'lazada'].map(platform => ({ platform, connected: false, mock: true })) })
    for (let index = 0; index < 2; index++) {
      const response = await fetch(`${endpoint}/shopee`, { method: 'PUT', headers: { Origin: origin } })
      expect(await response.json()).toEqual({ platform: 'shopee', connected: true, mock: true })
    }
    expect(await (await fetch(endpoint)).json()).toEqual({ connections: [
      { platform: 'shopee', connected: true, mock: true }, { platform: 'shopify', connected: false, mock: true }, { platform: 'lazada', connected: false, mock: true },
    ] })
    expect((await fetch(`${endpoint}/shopify`, { method: 'PUT' })).status).toBe(200)
    const fresh = await start()
    expect(await (await fetch(`${fresh}/api/mock/connectors`)).json()).toMatchObject({ connections: [{ connected: false }, { connected: false }, { connected: false }] })
  })

  it('rejects unknown platforms, methods, paths and cross-origin writes without changing flags', async () => {
    const origin = await start()
    for (const [path, method, headers, status] of [
      ['/api/mock/connectors/amazon', 'PUT', {}, 400],
      ['/api/mock/connectors/amazon', 'DELETE', {}, 400],
      ['/api/mock/connectors/tiktok', 'PUT', {}, 400],
      ['/api/mock/connectors/tiktok', 'DELETE', {}, 400],
      ['/api/mock/connectors', 'POST', {}, 405],
      ['/api/mock/connectors', 'DELETE', {}, 405],
      ['/api/mock/connectors/shopee', 'GET', {}, 405],
      ['/api/mock/unknown', 'GET', {}, 404],
      ['/api/mock/connectors/shopee/extra', 'PUT', {}, 404],
      ['/api/mock/connectors/shopee/extra', 'DELETE', {}, 404],
      ['/api/mock/connectors/shopee', 'PUT', { Origin: 'https://other.example' }, 403],
      ['/api/mock/connectors/shopee', 'PUT', { Origin: 'null' }, 403],
    ] as const) {
      const response = await fetch(`${origin}${path}`, { method, headers })
      expect(response.status).toBe(status)
      expect(response.headers.get('access-control-allow-origin')).toBeNull()
    }
    const response = await fetch(`${origin}/api/mock/connectors`)
    expect(await response.json()).toMatchObject({ connections: [{ connected: false }, { connected: false }, { connected: false }] })
  })

  it.each(['shopee', 'shopify', 'lazada'])('disconnects only %s, repeats safely and allows reconnection', async platform => {
    const origin = await start()
    const endpoint = `${origin}/api/mock/connectors`
    for (const name of ['shopee', 'shopify', 'lazada']) {
      expect((await fetch(`${endpoint}/${name}`, { method: 'PUT' })).status).toBe(200)
    }
    for (const Origin of ['https://other.example', 'null']) {
      expect((await fetch(`${endpoint}/${platform}`, { method: 'DELETE', headers: { Origin } })).status).toBe(403)
    }
    expect(await (await fetch(endpoint)).json()).toMatchObject({ connections: [{ connected: true }, { connected: true }, { connected: true }] })
    for (let index = 0; index < 2; index++) {
      const response = await fetch(`${endpoint}/${platform}`, { method: 'DELETE', headers: { Origin: origin } })
      expect(response.status).toBe(200)
      expect(response.headers.get('Cache-Control')).toBe('no-store')
      expect(await response.json()).toEqual({ platform, connected: false, mock: true })
    }
    expect(await (await fetch(endpoint)).json()).toEqual({ connections: ['shopee', 'shopify', 'lazada'].map(name => ({ platform: name, connected: name !== platform, mock: true })) })
    expect(await (await fetch(`${endpoint}/${platform}`, { method: 'PUT' })).json()).toEqual({ platform, connected: true, mock: true })
    const unsupported = await fetch(`${endpoint}/${platform}`, { method: 'PATCH' })
    expect(unsupported.status).toBe(405)
    expect(unsupported.headers.get('Allow')).toBe('PUT, DELETE')
  })

  it.each(['PUT', 'DELETE'])('accepts HTTPS %s forwarded by nginx behind CapRover', async method => {
    const origin = await start()
    await fetch(`${origin}/api/mock/connectors/shopee`, { method: 'PUT' })
    const response = await fetch(`${origin}/api/mock/connectors/shopee`, {
      method, headers: { Origin: origin.replace('http:', 'https:'), 'X-Forwarded-Proto': 'https' },
    })
    expect(response.status).toBe(200)
    expect(await response.json()).toMatchObject({ platform: 'shopee', connected: method === 'PUT' })
  })
})
