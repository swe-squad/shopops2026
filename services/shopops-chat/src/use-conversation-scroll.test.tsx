import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useConversationScroll } from './use-conversation-scroll'
import type { Message } from './workspace-api'

const messages: Message[] = [{ id: 1, role: 'assistant', text: 'Shipping update', created_at: '2026-10-31T09:00:00Z' }]

function Conversation({ items = messages }: { items?: Message[] }) {
  const { conversation, content, awayFromLatest, onScroll, jumpToLatest } = useConversationScroll(items, false, '')
  return <>
    <div ref={conversation} role="log" aria-label="Conversation" onScroll={onScroll}>
      <div ref={content}>{items[0].text}</div>
    </div>
    {awayFromLatest && <button onClick={jumpToLatest}>Jump to latest</button>}
  </>
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('conversation scrolling', () => {
  it.each(['wheel', 'PageUp', 'Home', 'ArrowUp', 'Shift+Space', 'touch'])('pauses following on %s intent before a delayed native scroll event', gesture => {
    const view = render(<Conversation />)
    const conversation = screen.getByRole('log', { name: 'Conversation' })
    let height = 1000
    let top = 600
    Object.defineProperties(conversation, {
      scrollHeight: { configurable: true, get: () => height },
      clientHeight: { configurable: true, value: 400 },
      scrollTop: { configurable: true, get: () => top, set: value => { top = Math.max(0, Math.min(value, height - 400)) } },
    })
    if (gesture === 'wheel') expect(fireEvent.wheel(conversation, { deltaY: -20000 })).toBe(true)
    else if (gesture === 'touch') {
      fireEvent.touchStart(conversation, { touches: [{ clientY: 100 }] })
      expect(fireEvent.touchMove(conversation, { touches: [{ clientY: 180 }] })).toBe(true)
    } else expect(fireEvent.keyDown(conversation, { key: gesture === 'Shift+Space' ? ' ' : gesture, shiftKey: gesture === 'Shift+Space' })).toBe(true)

    // A streamed line can render before the browser delivers its scroll event.
    height += 32
    view.rerender(<Conversation items={[{ ...messages[0], text: 'New streamed line' }]} />)
    expect(conversation.scrollTop).toBe(600)
    conversation.scrollTop = 0
    fireEvent.scroll(conversation)
    height += 32
    view.rerender(<Conversation items={[{ ...messages[0], text: 'Another streamed line' }]} />)
    expect(conversation.scrollTop).toBe(0)
    expect(screen.getByRole('button', { name: 'Jump to latest' })).toBeInTheDocument()
  })

  it('keeps following for downward gestures and leaves pinch zoom native', () => {
    const view = render(<Conversation />)
    const conversation = screen.getByRole('log', { name: 'Conversation' })
    let height = 1000
    let top = 600
    Object.defineProperties(conversation, {
      scrollHeight: { configurable: true, get: () => height },
      clientHeight: { configurable: true, value: 400 },
      scrollTop: { configurable: true, get: () => top, set: value => { top = Math.max(0, Math.min(value, height - 400)) } },
    })
    expect(fireEvent.wheel(conversation, { deltaY: 100 })).toBe(true)
    fireEvent.touchStart(conversation, { touches: [{ clientY: 100 }] })
    expect(fireEvent.touchMove(conversation, { touches: [{ clientY: 20 }] })).toBe(true)
    fireEvent.touchStart(conversation, { touches: [{ clientY: 100 }, { clientY: 200 }] })
    expect(fireEvent.touchMove(conversation, { touches: [{ clientY: 120 }, { clientY: 180 }] })).toBe(true)
    height += 32
    view.rerender(<Conversation items={[{ ...messages[0], text: 'New streamed line' }]} />)
    expect(conversation.scrollTop).toBe(632)
  })

  it('keeps followers at the end during viewport changes without moving someone reading above', () => {
    let notifyResize!: () => void
    const observe = vi.fn()
    const disconnect = vi.fn()
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { notifyResize = callback }
      observe = observe
      disconnect = disconnect
    })
    const view = render(<Conversation />)
    const conversation = screen.getByRole('log', { name: 'Conversation' })
    const remove = vi.spyOn(conversation, 'removeEventListener')
    let height = 1000
    let viewport = 400
    let top = 600
    Object.defineProperties(conversation, {
      scrollHeight: { configurable: true, get: () => height },
      clientHeight: { configurable: true, get: () => viewport },
      scrollTop: { configurable: true, get: () => top, set: value => { top = Math.max(0, Math.min(value, height - viewport)) } },
    })

    viewport = 250
    act(notifyResize)
    expect(conversation.scrollTop).toBe(750)
    conversation.scrollTop = 200
    fireEvent.scroll(conversation)
    height = 1200
    viewport = 300
    act(notifyResize)
    expect(conversation.scrollTop).toBe(200)
    fireEvent.click(screen.getByRole('button', { name: 'Jump to latest' }))
    expect(conversation.scrollTop).toBe(900)
    viewport = 400
    act(notifyResize)
    expect(conversation.scrollTop).toBe(800)
    expect(observe).toHaveBeenCalledWith(conversation)
    expect(observe).toHaveBeenCalledWith(conversation.firstElementChild)
    view.unmount()
    expect(disconnect).toHaveBeenCalledOnce()
    for (const event of ['wheel', 'keydown', 'touchstart', 'touchmove', 'touchend', 'touchcancel']) {
      expect(remove).toHaveBeenCalledWith(event, expect.any(Function))
    }
  })
})
