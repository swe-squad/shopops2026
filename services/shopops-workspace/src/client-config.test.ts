import { describe, expect, it } from 'vitest'
import { validateClientConfig } from './client-config'

const viewer = 'https://workspace.example.com'
const valid = { browser_url: 'https://browser.example.com', chat_url: 'https://chat.example.com' }

describe('public client configuration', () => {
  it('accepts separate HTTPS origins and local development origins', () => {
    expect(validateClientConfig(valid, viewer)).toEqual(valid)
    expect(validateClientConfig({ browser_url: 'http://127.0.0.1:5173', chat_url: 'http://localhost:5174' }, 'http://localhost:5175')).toEqual({ browser_url: 'http://127.0.0.1:5173', chat_url: 'http://localhost:5174' })
  })

  it.each(['javascript:alert(1)', 'data:text/html,hello', 'file:///tmp/app', 'http://external.example.com', 'https://user:pass@browser.example.com', 'https://browser.example.com/path', 'https://browser.example.com/', 'https://browser.example.com?token=secret', 'https://browser.example.com#fragment', 'https://browser.example.com\nhttps://other.example.com', 'https://browser.example.com\\page', ' https://browser.example.com'])('rejects unsafe or non-origin client URL %s', browser_url => {
    expect(() => validateClientConfig({ ...valid, browser_url }, viewer)).toThrow()
  })

  it('rejects clients on a shared origin after URL normalization', () => {
    expect(() => validateClientConfig({ browser_url: 'https://same.example.com', chat_url: 'https://SAME.example.com:443' }, viewer)).toThrow('separate origins')
  })

  it.each(['browser_url', 'chat_url'])('rejects the viewer itself as %s', key => {
    expect(() => validateClientConfig({ ...valid, [key]: viewer }, viewer)).toThrow('hosted separately')
  })

  it.each([null, [], {}, { browser_url: 5173, chat_url: true }])('rejects missing or malformed config %j', value => {
    expect(() => validateClientConfig(value, viewer)).toThrow()
  })
})
