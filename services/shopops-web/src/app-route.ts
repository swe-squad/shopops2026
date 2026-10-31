import { useCallback, useEffect, useState, type MouseEvent } from 'react'

export const defaultShopPath = '/shop/connections'

export function shopDestination(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return defaultShopPath
  try {
    // Reject encoded controls/backslashes too; never broaden this to arbitrary preview URLs.
    const decoded = decodeURIComponent(value)
    if (decoded.includes('\\') || Array.from(decoded).some(char => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127) || decoded.startsWith('//')) return defaultShopPath
    const url = new URL(value, window.location.origin)
    if (url.origin !== window.location.origin || !(url.pathname === '/shop' || url.pathname.startsWith('/shop/'))) return defaultShopPath
    return `${url.pathname}${url.search}${url.hash}`
  } catch {
    return defaultShopPath
  }
}

export function useAppRoute() {
  const [href, setHref] = useState(window.location.href)
  useEffect(() => {
    const update = () => setHref(window.location.href)
    window.addEventListener('popstate', update)
    return () => window.removeEventListener('popstate', update)
  }, [])
  const navigate = useCallback((path: string, replace = false) => {
    if (replace) window.history.replaceState(null, '', path)
    else window.history.pushState(null, '', path)
    setHref(window.location.href)
  }, [])

  function followLink(event: MouseEvent<HTMLElement>) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    const link = (event.target as Element).closest('a')
    if (!link || link.target || link.hasAttribute('download')) return
    const url = new URL(link.href)
    if (url.origin !== window.location.origin || (url.pathname === window.location.pathname && url.hash)) return
    event.preventDefault()
    navigate(`${url.pathname}${url.search}${url.hash}`)
  }

  return { url: new URL(href), navigate, followLink }
}
