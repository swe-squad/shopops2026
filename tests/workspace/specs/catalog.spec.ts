import { test, expect } from '@playwright/test'
import { browserApp, expectFixedParent, showClient, testToken, unlock } from './helpers'

const headers = { Authorization: `Bearer ${testToken}` }
const shopKey = 'shopee-open-platform:1001'
const productPath = `/shop/products?${new URLSearchParams({ shop_key: shopKey, sku: 'SHIRT-M' })}`

test('catalog uses authenticated source data and rejects foreign selections', async ({ request }) => {
  const base = 'http://127.0.0.1:8000/api/operations/catalog'
  expect((await request.get(`${base}/shops`)).status()).toBe(401)
  const shops = await request.get(`${base}/shops`, { headers })
  expect(shops.ok()).toBe(true)
  expect((await shops.json()).shops.map((shop: { shop_key: string }) => shop.shop_key)).toEqual([shopKey])
  const product = await request.get(`${base}/product`, {
    headers: { ...headers, 'X-Demo-User-Id': '+84900000002' },
    params: { shop_key: shopKey, sku: 'SHIRT-M' },
  })
  expect(product.ok()).toBe(true)
  const body = await product.json()
  expect(body.product).toMatchObject({ sku: 'SHIRT-M', available: 2, image_url: null, review_count: 4, negative_review_count: 2 })
  expect(body.reviews).toHaveLength(4)
  expect(body.returns).toHaveLength(1)
  expect((await request.get(`${base}/product`, { headers, params: { shop_key: 'shopee-open-platform:other', sku: 'SHIRT-M' } })).status()).toBe(404)
})

test('product gallery, evidence, mailbox navigation and polling share source records', async ({ page, request }) => {
  await page.goto('/')
  const browser = browserApp(page)
  await unlock(browser, 'Unlock workspace')
  await browser.getByRole('link', { name: 'Products', exact: true }).click()
  await expect(browser.getByRole('heading', { name: 'All products 3', exact: true })).toBeVisible()
  await browser.getByRole('searchbox', { name: 'Search products by name or SKU' }).fill('SHIRT-M')
  await expect(browser.getByRole('link', { name: /CAP.*Nón lưỡi trai/ })).not.toBeAttached()
  await browser.getByRole('link', { name: /SHIRT-M.*Áo thun cotton size M/ }).click()
  const details = browser.getByRole('region', { name: 'Product details' })
  await expect(details.getByRole('heading', { name: 'Áo thun cotton size M' })).toBeVisible()
  await expect(browser.getByLabel('Browser address')).toHaveValue(new RegExp('sku=SHIRT-M'))
  await browser.getByRole('tab', { name: 'Related returns 1', exact: true }).click()
  await expect(browser.getByText('A return on an order containing this product does not confirm that this SKU was returned.')).toBeVisible()
  await browser.getByRole('button', { name: 'Prepare question draft', exact: true }).click()
  await expect(browser.getByRole('textbox', { name: 'Investigation question · draft only' })).toHaveValue(/SKU SHIRT-M/)
  const stock = details.getByText('Observed available stock', { exact: true }).locator('..').locator('dd')
  await expect(stock).toHaveText('2')
  try {
    expect((await request.post('http://127.0.0.1:8000/__test/catalog/stock', { headers, data: { available: 13 } })).ok()).toBe(true)
    await expect(stock).toHaveText('13', { timeout: 7000 })
    await page.route('**/api/operations/catalog/product?*', route => route.fulfill({ status: 503, json: { detail: 'Offline fixture' } }))
    await expect(browser.getByText('Showing last good data · refresh failed')).toBeVisible({ timeout: 7000 })
    await expect(stock).toHaveText('13')
    await page.unroute('**/api/operations/catalog/product?*')
    await browser.getByRole('link', { name: 'Overview', exact: true }).click()
    expect((await request.post('http://127.0.0.1:8000/api/operations/navigation', { headers, data: { url: productPath } })).status()).toBe(201)
    await expect(details.getByRole('heading', { name: 'Áo thun cotton size M' })).toBeVisible()
    await expect(browser.getByLabel('Browser address')).toHaveValue(new RegExp('sku=SHIRT-M'))
    await expect(browser.getByRole('textbox', { name: 'Investigation question · draft only' })).toHaveValue(/SKU SHIRT-M/)
  } finally {
    await request.post('http://127.0.0.1:8000/__test/catalog/stock', { headers, data: { available: 2 } })
    await request.post('http://127.0.0.1:8000/api/operations/navigation', { headers, data: { url: '/shop/connections' } })
  }
})

for (const viewport of [{ width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }, { width: 844, height: 390 }]) {
  test(`product evidence fits independent viewer at ${viewport.width}×${viewport.height}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await showClient(page, 'Browser')
    const browser = browserApp(page)
    await unlock(browser, 'Unlock workspace')
    await browser.getByLabel('Browser address').fill(productPath)
    await browser.getByRole('button', { name: 'Open address', exact: true }).click()
    await expect(browser.getByRole('region', { name: 'Product details' }).getByRole('heading', { name: 'Áo thun cotton size M' })).toBeAttached()
    const horizontal = await browser.locator('.shop-page:visible').evaluate(element => ({ client: element.clientWidth, scroll: element.scrollWidth }))
    expect(horizontal.scroll).toBeLessThanOrEqual(horizontal.client + 1)
    await expect(browser.getByLabel('Browser address')).toBeInViewport()
    await expectFixedParent(page)
    await page.screenshot({ path: testInfo.outputPath('product-evidence.png') })
  })
}

test('standalone product URL opens the selected product after unlock', async ({ page }, testInfo) => {
  await page.goto(`http://localhost:5173${productPath}`)
  await page.getByLabel('Workspace access token').fill(testToken)
  await page.getByRole('button', { name: 'Unlock workspace', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Product details' }).getByRole('heading', { name: 'Áo thun cotton size M' })).toBeVisible()
  await expect(page.getByRole('img', { name: 'Áo thun cotton size M' })).not.toBeAttached()
  await expect(page.getByText('No product image', { exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('product-standalone.png') })
  await page.getByRole('link', { name: 'All products', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'All products 3', exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('product-gallery.png') })
})
