export function browserUrl(value: string, origin = window.location.origin): string | null {
  const input = value.trim()
  if (!input || Array.from(input).some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)) return null
  try {
    const url = new URL(input, origin)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null
    return url.href
  } catch {
    return null
  }
}

export function isLocalShop(url: URL) {
  return url.origin === window.location.origin && (url.pathname === '/shop' || url.pathname.startsWith('/shop/'))
}
