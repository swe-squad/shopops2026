import type { IncomingMessage, ServerResponse } from 'node:http'

export function createConnectorHandler() {
  const connected = { shopee: false, tiktok: false }
  const record = (platform: keyof typeof connected) => ({ platform, connected: connected[platform], mock: true })

  return (request: IncomingMessage, response: ServerResponse) => {
    const send = (status: number, body: unknown) => {
      response.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
      response.end(JSON.stringify(body))
    }
    const path = (request.url ?? '').split('?')[0]
    const base = '/api/mock/connectors'
    const platform = path.slice(base.length + 1)
    const item = path.startsWith(`${base}/`) && !platform.includes('/')
    if (path !== base && !item) return send(404, { error: 'Mock endpoint not found.' })
    if (item && platform !== 'shopee' && platform !== 'tiktok') return send(400, { error: 'Unknown platform.' })
    const method = item ? 'PUT' : 'GET'
    if (request.method !== method) {
      response.setHeader('Allow', method)
      return send(405, { error: 'Method not allowed.' })
    }
    if (item) {
      const protocol = request.headers['x-forwarded-proto'] === 'https' ? 'https' : 'http'
      if (request.headers.origin && request.headers.origin !== `${protocol}://${request.headers.host}`) {
        return send(403, { error: 'Cross-origin connection is not allowed.' })
      }
      connected[platform as keyof typeof connected] = true
      return send(200, record(platform as keyof typeof connected))
    }
    send(200, { connections: [record('shopee'), record('tiktok')] })
  }
}
