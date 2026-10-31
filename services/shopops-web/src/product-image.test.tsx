import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ProductImage } from './product-image'
import { safeProductImage } from './product-image-url'

afterEach(cleanup)
describe('product source images', () => {
  it.each([null, '', 'javascript:alert(1)', 'data:image/svg+xml,<svg/>', 'http://images.example.com/a.png', 'https://user:secret@example.com/a.png', 'https://example.com/\na.png', '/api/private'])('rejects an unsafe or missing URL: %s', url => {
    expect(safeProductImage(url)).toBeNull()
    render(<ProductImage url={url} name="Canvas tote" />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('No product image')).toBeInTheDocument()
  })

  it('uses no-referrer HTTPS images and replaces broken images with an honest placeholder', () => {
    const view = render(<ProductImage url="https://images.example.com/a.png" name="Canvas tote" />)
    const image = screen.getByRole('img', { name: 'Canvas tote' })
    expect(image).toHaveAttribute('referrerpolicy', 'no-referrer')
    fireEvent.error(image)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('Image unavailable')).toBeInTheDocument()
    view.rerender(<ProductImage url="https://images.example.com/replacement.png" name="Canvas tote" />)
    expect(screen.getByRole('img')).toHaveAttribute('src', 'https://images.example.com/replacement.png')
  })
})
