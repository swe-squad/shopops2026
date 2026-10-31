import { expect, type FrameLocator, type Page } from '@playwright/test'

export const testToken = 'workspace-browser-test-only'
export const browserApp = (page: Page) => page.frameLocator('iframe[title="Shop browser app"]')
export const chatApp = (page: Page) => page.frameLocator('iframe[title="Agent chat app"]')

export async function showClient(page: Page, client: 'Browser' | 'Chat') {
  const switcher = page.getByRole('button', { name: client, exact: true })
  if (await switcher.isVisible()) await switcher.click()
}

export async function unlock(frame: FrameLocator, button: string) {
  await frame.getByLabel('Workspace access token').fill(testToken)
  await frame.getByRole('button', { name: button, exact: true }).click()
}

export async function expectFixedParent(page: Page) {
  const bounds = await page.evaluate(() => ({
    width: innerWidth, height: innerHeight,
    scrollWidth: document.documentElement.scrollWidth,
    scrollHeight: document.documentElement.scrollHeight,
    bodyWidth: document.body.scrollWidth, bodyHeight: document.body.scrollHeight,
  }))
  expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width)
  expect(bounds.scrollHeight).toBeLessThanOrEqual(bounds.height)
  expect(bounds.bodyWidth).toBeLessThanOrEqual(bounds.width)
  expect(bounds.bodyHeight).toBeLessThanOrEqual(bounds.height)
  await page.mouse.move(4, 80)
  await page.mouse.wheel(0, 700)
  expect(await page.evaluate(() => scrollY)).toBe(0)
}
