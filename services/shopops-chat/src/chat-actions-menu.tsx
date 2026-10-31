import { useId, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

export function ChatActionsMenu({ busy, onReload, onLock }: { busy: boolean; onReload: () => void; onLock: () => void }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const initialFocus = useRef<'first' | 'last'>('first')
  const id = useId()

  function close(restoreFocus = false) {
    setOpen(false)
    if (restoreFocus) trigger.current?.focus({ preventScroll: true })
  }

  useLayoutEffect(() => {
    if (!open) return
    const items = menu.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')
    items?.[initialFocus.current === 'last' ? items.length - 1 : 0]?.focus({ preventScroll: true })
    function dismiss(event: PointerEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', dismiss)
    return () => document.removeEventListener('pointerdown', dismiss)
  }, [open])

  function moveFocus(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); return }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const items = Array.from(menu.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)') ?? [])
    const current = items.indexOf(document.activeElement as HTMLButtonElement)
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length
    items[next]?.focus({ preventScroll: true })
  }

  return <div className="chat-actions-menu" ref={root} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) close() }}>
    <button type="button" className="icon-button chat-menu-trigger" ref={trigger} aria-label="Chat menu" title="Chat menu" aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => { initialFocus.current = 'first'; setOpen(value => !value) }}
      onKeyDown={event => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); initialFocus.current = event.key === 'ArrowUp' ? 'last' : 'first'; setOpen(true) } }}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="5" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="12" cy="19" r="1.5" /></svg>
    </button>
    {open && <div className="chat-menu" id={id} ref={menu} role="menu" aria-label="Conversation actions" onKeyDown={moveFocus}>
      <button type="button" role="menuitem" tabIndex={-1} disabled={busy} onClick={() => { close(true); onReload() }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5M5.5 7a7.5 7.5 0 0 1 12.4-1.4L20 8M4 16l2.1 2.4A7.5 7.5 0 0 0 18.5 17" /></svg>Load conversation</button>
      <button type="button" role="menuitem" tabIndex={-1} onClick={() => { close(true); onLock() }}><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" /></svg>Lock</button>
    </div>}
  </div>
}
