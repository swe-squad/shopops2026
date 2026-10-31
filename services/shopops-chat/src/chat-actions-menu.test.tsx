import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatActionsMenu } from './chat-actions-menu'

afterEach(cleanup)

describe('conversation actions menu', () => {
  it('opens from the keyboard, moves between actions and restores focus on Escape', () => {
    render(<ChatActionsMenu busy={false} onReload={vi.fn()} onLock={vi.fn()} />)
    const trigger = screen.getByRole('button', { name: 'Chat menu' })
    fireEvent.keyDown(trigger, { key: 'ArrowDown' })
    const reload = screen.getByRole('menuitem', { name: 'Load conversation' })
    const lock = screen.getByRole('menuitem', { name: 'Lock' })
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(reload).toHaveFocus()
    fireEvent.keyDown(reload, { key: 'ArrowDown' })
    expect(lock).toHaveFocus()
    fireEvent.keyDown(lock, { key: 'Home' })
    expect(reload).toHaveFocus()
    fireEvent.keyDown(reload, { key: 'End' })
    expect(lock).toHaveFocus()
    fireEvent.keyDown(lock, { key: 'Escape' })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
    fireEvent.keyDown(trigger, { key: 'ArrowUp' })
    expect(screen.getByRole('menuitem', { name: 'Lock' })).toHaveFocus()
  })

  it('runs reload and closes, without invoking lock', () => {
    const reload = vi.fn()
    const lock = vi.fn()
    render(<ChatActionsMenu busy={false} onReload={reload} onLock={lock} />)
    fireEvent.click(screen.getByRole('button', { name: 'Chat menu' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Load conversation' }))
    expect(reload).toHaveBeenCalledOnce()
    expect(lock).not.toHaveBeenCalled()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Chat menu' })).toHaveFocus()
  })

  it('keeps lock available while a busy conversation disables reload', () => {
    const reload = vi.fn()
    const lock = vi.fn()
    render(<ChatActionsMenu busy onReload={reload} onLock={lock} />)
    fireEvent.click(screen.getByRole('button', { name: 'Chat menu' }))
    expect(screen.getByRole('menuitem', { name: 'Load conversation' })).toBeDisabled()
    const lockItem = screen.getByRole('menuitem', { name: 'Lock' })
    expect(lockItem).toHaveFocus()
    fireEvent.keyDown(lockItem, { key: 'ArrowDown' })
    expect(lockItem).toHaveFocus()
    fireEvent.click(lockItem)
    expect(lock).toHaveBeenCalledOnce()
    expect(reload).not.toHaveBeenCalled()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('dismisses on outside pointer or focus without moving focus back', () => {
    render(<><ChatActionsMenu busy={false} onReload={vi.fn()} onLock={vi.fn()} /><button>Outside</button></>)
    const trigger = screen.getByRole('button', { name: 'Chat menu' })
    const outside = screen.getByRole('button', { name: 'Outside' })
    fireEvent.click(trigger)
    fireEvent.pointerDown(outside)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    fireEvent.click(trigger)
    fireEvent.blur(screen.getByRole('menuitem', { name: 'Load conversation' }), { relatedTarget: outside })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(trigger).not.toHaveFocus()
  })
})
