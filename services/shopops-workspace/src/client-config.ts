export type ClientConfig = { browser_url: string; chat_url: string }

function clientOrigin(value: unknown, label: string) {
  const invalid = () => new Error(`The ${label} app URL must be an HTTPS origin, or a local HTTP origin for development.`)
  if (typeof value !== 'string' || value !== value.trim() || /[\s"'\\<>]/.test(value)) throw invalid()
  let url: URL
  try { url = new URL(value) } catch { throw invalid() }
  const authority = value.slice(value.indexOf('://') + 3)
  if (url.username || url.password || authority.includes('/') || url.pathname !== '/' || url.search || url.hash) throw invalid()
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))) throw invalid()
  return url.origin
}

export function validateClientConfig(value: unknown, viewerOrigin = window.location.origin): ClientConfig {
  if (!value || typeof value !== 'object') throw new Error('Client app configuration is missing.')
  const config = value as Record<string, unknown>
  const browser_url = clientOrigin(config.browser_url, 'browser')
  const chat_url = clientOrigin(config.chat_url, 'chat')
  const viewer = new URL(viewerOrigin).origin
  if (browser_url === chat_url) throw new Error('The browser and chat apps need separate origins.')
  if (browser_url === viewer || chat_url === viewer) throw new Error('Client apps must be hosted separately from this viewer.')
  return { browser_url, chat_url }
}
