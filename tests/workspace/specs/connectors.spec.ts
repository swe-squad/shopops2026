import { test, expect } from '@playwright/test'
import { browserApp, expectFixedParent, showClient, testToken, unlock } from './helpers'

test('mock connections survive browser reload and relogin and are shared by the service', async ({ page, browser }) => {
  const mockHeaders: Record<string, string>[] = []
  page.on('request', request => { if (request.url().includes('/api/mock/')) mockHeaders.push(request.headers()) })
  const open = async (target: typeof page) => {
    await target.goto('http://localhost:5173/')
    await target.getByLabel('Workspace access token').fill(testToken)
    await target.getByRole('button', { name: 'Unlock workspace' }).click()
    await expect(target.getByRole('heading', { name: 'Connect your stores' })).toBeVisible()
  }
  await open(page)
  await expect(page.getByRole('region', { name: 'Shopee' })).toContainText('Not connected')
  await expect(page.getByRole('region', { name: 'TikTok' })).toContainText('Not connected')
  await page.getByRole('button', { name: 'Log in to Shopee' }).click()
  await expect(page.getByRole('heading', { name: 'Connection successful' })).toBeVisible()
  await expect(page.getByLabel('Browser address')).toHaveValue(/\/shop\/connections\/shopee\/success$/)
  await page.getByRole('button', { name: 'Lock workspace' }).click()
  await page.getByLabel('Workspace access token').fill(testToken)
  await page.getByRole('button', { name: 'Unlock workspace' }).click()
  await expect(page.getByRole('button', { name: 'View Shopee connection' })).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Workspace access token')).toHaveValue('')
  await page.getByLabel('Workspace access token').fill(testToken)
  await page.getByRole('button', { name: 'Unlock workspace' }).click()
  await expect(page.getByRole('button', { name: 'View Shopee connection' })).toBeVisible()
  const other = await browser.newContext()
  try {
    const second = await other.newPage()
    await open(second)
    await expect(second.getByRole('button', { name: 'View Shopee connection' })).toBeVisible()
    await second.getByRole('button', { name: 'Log in to TikTok' }).click()
    await expect(second.getByRole('heading', { name: 'Connection successful' })).toBeVisible()
    await page.getByRole('button', { name: 'Reload page', exact: true }).click()
    await expect(page.getByRole('button', { name: 'View TikTok connection' })).toBeVisible()
  } finally { await other.close() }
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 })
  expect(mockHeaders.length).toBeGreaterThan(0)
  expect(mockHeaders.every(headers => !headers.authorization && !headers.cookie)).toBe(true)
})

test('connector pages fit the embedded viewport and preserve tab keyboard focus', async ({ page, request }, testInfo) => {
  for (const platform of ['shopee', 'tiktok']) {
    expect((await request.put(`http://localhost:5173/api/mock/connectors/${platform}`)).ok()).toBe(true)
  }
  await page.goto('/')
  const app = browserApp(page)
  await unlock(app, 'Unlock workspace')
  await expect(app.getByRole('button', { name: 'View Shopee connection' })).toBeVisible()
  await app.getByRole('button', { name: 'New browser tab' }).click()
  await app.getByRole('tab', { selected: true }).press('Home')
  await expect(app.getByRole('tab', { name: 'Connections — tab 1' })).toBeFocused()
  for (const viewport of [{ width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }, { width: 844, height: 390 }]) {
    await page.setViewportSize(viewport)
    await showClient(page, 'Browser')
    await expect(app.getByRole('heading', { name: 'Connect your stores' })).toBeVisible()
    await expect(app.getByRole('button', { name: 'View Shopee connection' })).toBeVisible()
    const bounds = await app.locator('html').evaluate(element => ({ width: window.innerWidth, height: window.innerHeight, scrollWidth: element.scrollWidth, scrollHeight: element.scrollHeight }))
    expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width)
    expect(bounds.scrollHeight).toBeLessThanOrEqual(bounds.height)
    await expectFixedParent(page)
    await page.screenshot({ path: testInfo.outputPath(`connections-${viewport.width}.png`) })
  }
  await app.getByRole('button', { name: 'View TikTok connection' }).click()
  await expect(app.getByRole('heading', { name: 'Connection successful' })).toBeVisible()
  await expectFixedParent(page)
})
