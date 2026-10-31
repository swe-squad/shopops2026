import { describe, expect, it } from 'vitest'
import { conversationDay } from './conversation-date'

describe('conversation day labels', () => {
  it('labels actual messages from the current local day as Today', () => {
    const now = new Date(2026, 9, 31, 15)
    expect(conversationDay(new Date(2026, 9, 31, 9).toISOString(), now)).toEqual({ key: '2026-10-31', label: 'Today' })
    expect(conversationDay(new Date(2026, 9, 30, 23).toISOString(), now)?.label).not.toBe('Today')
  })

  it('keeps past years explicit and omits unparseable dates', () => {
    const day = conversationDay(new Date(2025, 0, 2, 12).toISOString(), new Date(2026, 9, 31, 15))
    expect(day?.key).toBe('2025-01-02')
    expect(day?.label).toContain('2025')
    expect(conversationDay('not-a-date')).toBeNull()
  })
})
