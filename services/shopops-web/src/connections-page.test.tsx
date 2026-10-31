import { useState } from 'react'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ConnectionsPage } from './connections-page'
import { connectionPage } from './browser-url'
import { useMockConnectors } from './use-mock-connectors'

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
const list = (shopee = false, shopify = false, lazada = false) => ({ connections: [{ platform: 'shopee', connected: shopee, mock: true }, { platform: 'shopify', connected: shopify, mock: true }, { platform: 'lazada', connected: lazada, mock: true }] })
function Demo({ initial = '/shop/connections' }: { initial?: string }) {
  const data = useMockConnectors()
  const [path, navigate] = useState(initial)
  return <ConnectionsPage page={connectionPage(path)!} data={data} active reload={0} onNavigate={navigate} />
}
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it.each(['Shopee', 'Shopify', 'Lazada'])('connects %s and returns to the list with independent status', async name => {
  const platform = name.toLowerCase()
  let connected = false
  const fetchMock = vi.fn(async (_url: string, options?: RequestInit) => {
    if (options?.method === 'PUT') { connected = true; return json({ platform, connected: true, mock: true }) }
    return json(list(connected && platform === 'shopee', connected && platform === 'shopify', connected && platform === 'lazada'))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<Demo />)
  await screen.findAllByText('Not connected')
  expect(screen.getAllByRole('region').map(region => within(region).getByRole('heading').textContent)).toEqual(['Shopee', 'Shopify', 'Lazada'])
  expect(screen.queryByRole('region', { name: 'TikTok' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: `Log in to ${name}` }))
  await screen.findByRole('heading', { name: 'Connection successful' })
  expect(screen.getByRole('heading', { name: `${name} connection` })).toHaveFocus()
  expect(fetchMock).toHaveBeenCalledWith(`/api/mock/connectors/${platform}`, expect.objectContaining({ method: 'PUT' }))
  fireEvent.click(screen.getByRole('button', { name: 'Back to connections' }))
  await screen.findByRole('button', { name: `View ${name} connection` })
  for (const other of ['Shopee', 'Shopify', 'Lazada']) {
    expect(within(screen.getByRole('region', { name: other })).getByText(other === name ? 'Connected' : 'Not connected')).toBeInTheDocument()
  }
  fireEvent.click(screen.getByRole('button', { name: `View ${name} connection` }))
  await screen.findByRole('heading', { name: 'Connection successful' })
})

it('shows save failure without success and can check again after a lost response', async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(json(list())).mockRejectedValueOnce(new Error('offline')).mockResolvedValue(json(list(true)))
  vi.stubGlobal('fetch', fetchMock)
  render(<Demo />)
  await screen.findAllByText('Not connected')
  fireEvent.click(screen.getByRole('button', { name: 'Log in to Shopee' }))
  await screen.findByRole('alert')
  expect(screen.queryByText('Connection successful')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Check again' }))
  await screen.findByRole('button', { name: 'View Shopee connection' })
})

it('does not connect from a direct success URL or navigate on a response after unmount', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json(list()))
  vi.stubGlobal('fetch', fetchMock)
  const view = render(<Demo initial="/shop/connections/shopify/success" />)
  await screen.findByRole('heading', { name: 'Not connected yet' })
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(fetchMock.mock.calls[0][1].method).toBe('GET')
  view.unmount()
  let resolveSave!: (value: Response) => void
  fetchMock.mockResolvedValueOnce(json(list())).mockImplementationOnce(() => new Promise<Response>(resolve => { resolveSave = resolve }))
  const second = render(<Demo />)
  await screen.findAllByText('Not connected')
  fireEvent.click(screen.getByRole('button', { name: 'Log in to Shopify' }))
  expect(screen.getByRole('button', { name: /Connecting/ })).toBeDisabled()
  second.unmount()
  await act(async () => resolveSave(json({ platform: 'shopify', connected: true, mock: true })))
  expect(screen.queryByText('Connection successful')).not.toBeInTheDocument()
  expect(connectionPage('/shop/connections/unknown/success')).toBeNull()
})
