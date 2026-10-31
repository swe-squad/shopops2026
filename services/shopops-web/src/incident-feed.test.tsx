import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IncidentFeed } from './incident-feed'

beforeEach(() => vi.stubEnv('TZ', 'Asia/Ho_Chi_Minh'))
afterEach(() => { cleanup(); vi.unstubAllEnvs() })

describe('incident timestamps', () => {
  it.each([
    '2026-10-31 06:26:00',
    '2026-10-31T06:26:00',
    '2026-10-31T06:26:00Z',
    '2026-10-31T13:26:00+07:00',
  ])('renders %s in the seller timezone and exposes the same instant in dateTime', createdAt => {
    const expected = new Date('2026-10-31T06:26:00Z')
    expect(expected.getHours()).toBe(13)
    render(<IncidentFeed incidents={[{ id: 7, title: 'Carrier handoff', detail: '', created_at: createdAt }]} loading={false} error="" onRetry={() => {}} prefix="time-test" />)
    const time = screen.getByRole('article').querySelector('time')
    expect(time).toHaveTextContent(expected.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }))
    expect(time).toHaveAttribute('dateTime', '2026-10-31T06:26:00.000Z')
  })
})

it('shows the recent-record limit only when the visible feed reaches 100 records', () => {
  const incidents = Array.from({ length: 100 }, (_, index) => ({ id: index + 1, title: `Incident ${index + 1}`, detail: '', created_at: '2026-10-31T06:26:00Z' }))
  const view = render(<IncidentFeed incidents={incidents.slice(0, 99)} loading={false} error="" onRetry={() => {}} prefix="limit-test" />)
  expect(screen.queryByText('Showing the 100 most recent incidents.')).not.toBeInTheDocument()
  view.rerender(<IncidentFeed incidents={incidents} loading={false} error="" onRetry={() => {}} prefix="limit-test" />)
  expect(screen.getByText('Showing the 100 most recent incidents.')).toBeInTheDocument()
  expect(screen.getAllByRole('article')).toHaveLength(100)
})
