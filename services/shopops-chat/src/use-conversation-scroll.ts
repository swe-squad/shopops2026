import { useLayoutEffect, useRef, useState } from 'react'
import type { Message } from './workspace-api'

export function useConversationScroll(messages: Message[], loading: boolean, error: string) {
  const conversation = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const following = useRef(true)
  const previousMessages = useRef(messages)
  const [awayFromLatest, setAwayFromLatest] = useState(false)
  const [hasNewContent, setHasNewContent] = useState(false)

  function scrollToEnd() {
    const element = conversation.current
    if (element) element.scrollTop = element.scrollHeight
  }

  function jumpToLatest() {
    following.current = true
    setAwayFromLatest(false)
    setHasNewContent(false)
    scrollToEnd()
  }

  function onScroll() {
    const element = conversation.current
    if (!element) return
    const nearEnd = element.scrollHeight - element.scrollTop - element.clientHeight <= 64
    following.current = nearEnd
    setAwayFromLatest(!nearEnd)
    if (nearEnd) setHasNewContent(false)
  }

  useLayoutEffect(() => {
    const changed = previousMessages.current !== messages
    previousMessages.current = messages
    if (following.current) scrollToEnd()
    else if (changed) setHasNewContent(true)
  }, [messages, loading, error])

  useLayoutEffect(() => {
    const element = conversation.current
    if (!element) return
    let touchY: number | undefined
    const pauseFollowing = () => {
      if (element.scrollHeight > element.clientHeight) following.current = false
    }
    const onWheel = (event: WheelEvent) => { if (event.deltaY < 0) pauseFollowing() }
    const onKeyDown = (event: KeyboardEvent) => {
      if (['ArrowUp', 'PageUp', 'Home'].includes(event.key) || (event.key === ' ' && event.shiftKey)) pauseFollowing()
    }
    const onTouchStart = (event: TouchEvent) => { touchY = event.touches.length === 1 ? event.touches[0].clientY : undefined }
    const onTouchMove = (event: TouchEvent) => {
      const nextY = event.touches.length === 1 ? event.touches[0].clientY : undefined
      if (touchY !== undefined && nextY !== undefined && nextY > touchY) pauseFollowing()
      touchY = nextY
    }
    const onTouchEnd = () => { touchY = undefined }
    // Deliver scroll intent before compositor scrolling; a same-frame stream update must not
    // shift its starting offset. Native scrolling and pinch zoom remain untouched.
    element.addEventListener('wheel', onWheel, { passive: false })
    element.addEventListener('keydown', onKeyDown)
    element.addEventListener('touchstart', onTouchStart, { passive: true })
    element.addEventListener('touchmove', onTouchMove, { passive: false })
    element.addEventListener('touchend', onTouchEnd, { passive: true })
    element.addEventListener('touchcancel', onTouchEnd, { passive: true })

    // Keyboard/composer resizing must keep followers at the end without moving readers.
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(() => {
      if (following.current) scrollToEnd()
    })
    observer?.observe(element)
    if (content.current) observer?.observe(content.current)
    return () => {
      observer?.disconnect()
      element.removeEventListener('wheel', onWheel)
      element.removeEventListener('keydown', onKeyDown)
      element.removeEventListener('touchstart', onTouchStart)
      element.removeEventListener('touchmove', onTouchMove)
      element.removeEventListener('touchend', onTouchEnd)
      element.removeEventListener('touchcancel', onTouchEnd)
    }
  }, [])

  return { conversation, content, awayFromLatest, hasNewContent, onScroll, jumpToLatest }
}
