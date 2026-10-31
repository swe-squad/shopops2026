import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('workspace', () => {
  it('navigates between shop views and the agent chat', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /your shop, in good hands/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /view all/i }))
    expect(screen.getByRole('heading', { name: 'No incidents to show yet' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /open agent chat/i }))
    expect(screen.getByText(/integration coming soon/i)).toBeInTheDocument()
  })
})
