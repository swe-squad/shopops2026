import { test, expect } from '@playwright/test'
import { browserApp, chatApp, expectFixedParent, showClient, unlock } from './helpers'

const viewports = [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
  { width: 844, height: 390 },
]

for (const viewport of viewports) {
  test(`parent stays fixed at ${viewport.width}×${viewport.height}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await expect(browserApp(page).getByRole('heading', { name: 'Clarity in the chaos.' })).toBeVisible()
    await expectFixedParent(page)
    await showClient(page, 'Chat')
    await expect(chatApp(page).getByLabel('Workspace access token')).toBeVisible()
    if (viewport.width <= 900) {
      const hiddenBrowser = page.locator('iframe[title="Shop browser app"]')
      await expect(hiddenBrowser).toBeHidden()
      const bounds = await hiddenBrowser.evaluate(element => ({ width: element.getBoundingClientRect().width, height: element.getBoundingClientRect().height }))
      expect(bounds.width).toBeGreaterThan(0)
      expect(bounds.height).toBeGreaterThan(200)
      await page.getByRole('button', { name: 'Chat', exact: true }).focus()
      await page.keyboard.press('Tab')
      await expect(page.getByRole('button', { name: 'Reload chat app' })).toBeFocused()
    }
    await expectFixedParent(page)
    await unlock(chatApp(page), 'Unlock chat')
    await expect(chatApp(page).getByLabel('Message', { exact: true })).toBeInViewport()
    await showClient(page, 'Browser')
    await unlock(browserApp(page), 'Unlock workspace')
    await expect(browserApp(page).getByLabel('Browser address')).toBeInViewport()
    await expect(browserApp(page).getByRole('button', { name: 'New browser tab' })).toBeInViewport()
    await expectFixedParent(page)
    await showClient(page, 'Chat')
    for (const title of ['Shop browser app', 'Agent chat app']) {
      const frame = page.locator(`iframe[title="${title}"]`)
      if (await frame.isVisible()) {
        const box = await frame.boundingBox()
        expect(box).not.toBeNull()
        expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height)
        expect(box!.height).toBeGreaterThan(200)
      }
    }
    await page.screenshot({ path: testInfo.outputPath('workspace.png') })
  })
}

test('child origins stay isolated and viewer holds no credentials', async ({ page }) => {
  const ownRequests: string[] = []
  page.on('request', request => {
    if (request.frame() === page.mainFrame()) ownRequests.push(request.url())
  })
  await page.goto('/')
  await expect(browserApp(page).getByRole('heading', { name: 'Clarity in the chaos.' })).toBeVisible()
  await expect(chatApp(page).getByLabel('Workspace access token')).toBeVisible()
  const children = page.frames().filter(frame => frame.parentFrame() === page.mainFrame())
  expect(children).toHaveLength(2)
  expect(new Set(children.map(frame => new URL(frame.url()).origin)).size).toBe(2)
  for (const frame of children) {
    expect(await frame.evaluate(() => {
      try { void parent.document.body; return false } catch { return true }
    })).toBe(true)
  }
  expect(ownRequests.filter(url => url.includes('/api/'))).toEqual([])
  expect(await page.locator('input, textarea').count()).toBe(0)
})
