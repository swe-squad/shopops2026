import { useLayoutEffect, useRef } from 'react'

export function useMobileViewport() {
  const shell = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const viewport = window.visualViewport
    const element = shell.current
    // Embedded documents follow their iframe. Only the standalone page follows its keyboard.
    if (!viewport || !element || window.self !== window.top) return
    function resize() {
      if (!viewport || !element) return
      if (viewport.scale !== 1) {
        element.style.removeProperty('--app-height')
        element.style.removeProperty('--viewport-offset')
        return
      }
      element.style.setProperty('--app-height', `${viewport.height}px`)
      element.style.setProperty('--viewport-offset', `${viewport.offsetTop}px`)
    }
    resize()
    viewport.addEventListener('resize', resize)
    viewport.addEventListener('scroll', resize)
    return () => {
      viewport.removeEventListener('resize', resize)
      viewport.removeEventListener('scroll', resize)
    }
  }, [])

  return shell
}
