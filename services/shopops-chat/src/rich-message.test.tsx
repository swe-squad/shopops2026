import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { browserUrl } from './browser-url'
import { RichMessage } from './rich-message'

afterEach(cleanup)

describe('safe message navigation', () => {
  it.each(['javascript:alert(1)', 'data:text/html,hello', 'file:///private/tmp/a', 'https://user:pass@example.com', 'https://example.com/\npage'])('rejects unsafe address %s', value => {
    expect(browserUrl(value)).toBeNull()
  })

  it('accepts local shop routes and external HTTP URLs', () => {
    expect(browserUrl('/shop/incidents#incident-3')).toBe('/shop/incidents#incident-3')
    expect(browserUrl('https://example.com/orders?q=3')).toBe('https://example.com/orders?q=3')
  })

  it('removes active HTML and unsafe links while making ordinary URLs navigate through the shell', () => {
    const navigate = vi.fn()
    render(<RichMessage text={'[Unsafe](javascript:alert%281%29)\n\n<script>alert(1)</script>\n\n![tracking](https://example.com/pixel)\n\nhttps://example.com/orders'} onNavigate={navigate} />)
    expect(screen.queryByRole('link', { name: 'Unsafe' })).not.toBeInTheDocument()
    expect(document.querySelector('script, img, iframe')).toBeNull()
    expect(screen.getByText('[Image: tracking]')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: 'https://example.com/orders' }))
    expect(navigate).toHaveBeenCalledWith('https://example.com/orders')
  })
})
