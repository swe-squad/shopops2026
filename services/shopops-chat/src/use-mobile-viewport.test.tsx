import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useMobileViewport } from './use-mobile-viewport'

function ViewportShell() {
  const shell = useMobileViewport()
  return <div ref={shell} role="region" aria-label="Mobile app" />
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('standalone mobile viewport', () => {
  it('tracks the visible keyboard viewport and cleans up its listeners', () => {
    const viewport = Object.assign(new EventTarget(), { height: 812, offsetTop: 0, scale: 1 })
    const remove = vi.spyOn(viewport, 'removeEventListener')
    vi.stubGlobal('visualViewport', viewport)
    const view = render(<ViewportShell />)
    const shell = screen.getByRole('region', { name: 'Mobile app' })
    expect(shell.style.getPropertyValue('--app-height')).toBe('812px')
    act(() => {
      viewport.height = 420
      viewport.offsetTop = 16
      viewport.dispatchEvent(new Event('resize'))
    })
    expect(shell.style.getPropertyValue('--app-height')).toBe('420px')
    expect(shell.style.getPropertyValue('--viewport-offset')).toBe('16px')
    view.unmount()
    expect(remove).toHaveBeenCalledWith('resize', expect.any(Function))
    expect(remove).toHaveBeenCalledWith('scroll', expect.any(Function))
  })

  it('leaves pinch zoom to the browser and uses CSS when the viewport API is absent', () => {
    const viewport = Object.assign(new EventTarget(), { height: 812, offsetTop: 0, scale: 1 })
    vi.stubGlobal('visualViewport', viewport)
    const view = render(<ViewportShell />)
    const shell = screen.getByRole('region', { name: 'Mobile app' })
    act(() => { viewport.scale = 2; viewport.dispatchEvent(new Event('resize')) })
    expect(shell.style.getPropertyValue('--app-height')).toBe('')
    expect(shell.style.getPropertyValue('--viewport-offset')).toBe('')
    view.unmount()
    vi.stubGlobal('visualViewport', undefined)
    render(<ViewportShell />)
    expect(screen.getByRole('region', { name: 'Mobile app' }).style.getPropertyValue('--app-height')).toBe('')
  })

  it('lets an embedded client follow its frame instead of the top-level viewport', () => {
    const viewport = Object.assign(new EventTarget(), { height: 812, offsetTop: 48, scale: 1 })
    const listen = vi.spyOn(viewport, 'addEventListener')
    vi.stubGlobal('visualViewport', viewport)
    vi.stubGlobal('self', {})
    render(<ViewportShell />)
    const shell = screen.getByRole('region', { name: 'Mobile app' })
    expect(shell.style.getPropertyValue('--app-height')).toBe('')
    expect(shell.style.getPropertyValue('--viewport-offset')).toBe('')
    expect(listen).not.toHaveBeenCalled()
  })
})
