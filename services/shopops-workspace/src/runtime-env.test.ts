/// <reference types="node" />
import { spawnSync } from 'node:child_process'
import process from 'node:process'
import { describe, expect, it } from 'vitest'

function validate(browser: string | undefined, chat = 'https://chat.example.com') {
  return spawnSync('/bin/sh', ['./require-env.sh'], {
    cwd: process.cwd(), encoding: 'utf8',
    env: { PATH: process.env.PATH, ...(browser === undefined ? {} : { BROWSER_APP_URL: browser }), CHAT_APP_URL: chat },
  })
}

describe('runtime origin interpolation boundary', () => {
  it.each(['https://browser.example.com', 'https://browser.example.com:8443', 'https://127.0.0.1:8443', 'http://localhost:5173', 'http://127.0.0.1:5173'])('accepts safe origin %s', browser => {
    expect(validate(browser).status).toBe(0)
  })

  it.each([undefined, '', 'http://browser.example.com', 'https://browser.example.com/', 'https://browser.example.com/path', 'https://user:pass@browser.example.com', 'https://browser.example.com?x=y', 'https://browser.example.com#hash', 'https://browser.example.com:0', 'https://browser.example.com:65536', 'https://browser.example.com:999999', 'https://browser.example.com\nhttps://evil.example.com', 'https://browser.example.com\r', 'https://browser.example.com";', "https://browser.example.com'", 'https://browser.example.com;add_header', 'https://bad..example.com', 'https://-bad.example.com', 'https://999.999.999.999'])('blocks invalid or injection-bearing runtime value %j', browser => {
    expect(validate(browser).status).not.toBe(0)
  })

  it('validates chat independently and rejects a normalized shared origin', () => {
    expect(validate('https://browser.example.com', 'https://chat.example.com\nhttps://evil.example.com').status).not.toBe(0)
    expect(validate('https://same.example.com', 'https://SAME.example.com:443').status).not.toBe(0)
  })
})
