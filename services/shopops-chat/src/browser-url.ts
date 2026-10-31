export function browserUrl(value: string, origin = window.location.origin): string | null {
  const input = value.trim()
  if (!input || Array.from(input).some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)) return null
  try {
    if (!/^(https?:\/\/|\/)/i.test(input)) return null
    const url = new URL(input, origin)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null
    // Shop routes belong to the separately hosted browser app, never this chat origin.
    if (input.startsWith('/') && !input.startsWith('//')) {
      if (url.pathname !== '/shop' && !url.pathname.startsWith('/shop/')) return null
      return `${url.pathname}${url.search}${url.hash}`
    }
    return url.href
  } catch {
    return null
  }
}


export function displayTime(value: string) {
  const timestamp = new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  return Number.isNaN(timestamp.getTime()) ? '' : timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
