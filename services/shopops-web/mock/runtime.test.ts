// @vitest-environment node
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { afterEach, expect, it } from 'vitest'

const children: ReturnType<typeof spawn>[] = []
async function start(command = process.execPath, args = ['-e', "console.log('child:' + process.pid); setInterval(() => {}, 1000)"]) {
  const script = `import { startRuntime } from './mock/runtime.ts'; const server = startRuntime(${JSON.stringify(command)}, ${JSON.stringify(args)}, 0); server.on('listening', () => console.log('port:' + server.address().port))`
  const child = spawn(process.execPath, ['--input-type=module', '-e', script], { stdio: ['ignore', 'pipe', 'pipe'] })
  children.push(child)
  const exited = once(child, 'exit')
  let output = ''
  child.stdout.on('data', chunk => { output += chunk.toString() })
  child.stderr.resume()
  await expect.poll(() => output).toMatch(/port:\d+/)
  return { child, exited, output: () => output, url: `http://127.0.0.1:${/port:(\d+)/.exec(output)![1]}/api/mock/connectors` }
}
afterEach(async () => {
  await Promise.all(children.splice(0).map(async child => {
    if (child.exitCode === null && child.signalCode === null) {
      const closed = once(child, 'exit')
      child.kill('SIGTERM')
      await closed
    }
  }))
})

it('keeps RAM across real HTTP calls, stops both processes, and resets on restart', async () => {
  const runtime = await start()
  await expect.poll(runtime.output).toMatch(/child:\d+/)
  const nginxPid = Number(/child:(\d+)/.exec(runtime.output())![1])
  expect((await fetch(`${runtime.url}/shopee`, { method: 'PUT' })).status).toBe(200)
  expect(await (await fetch(runtime.url)).json()).toMatchObject({ connections: [{ connected: true }, { connected: false }] })
  expect(await (await fetch(`${runtime.url}/shopee`, { method: 'DELETE' })).json()).toEqual({ platform: 'shopee', connected: false, mock: true })
  expect(await (await fetch(runtime.url)).json()).toMatchObject({ connections: [{ connected: false }, { connected: false }] })
  expect((await fetch(`${runtime.url}/shopee`, { method: 'PUT' })).status).toBe(200)
  runtime.child.kill('SIGTERM')
  expect((await runtime.exited)[0]).toBe(0)
  expect(() => process.kill(nginxPid, 0)).toThrow()
  const fresh = await start()
  expect(await (await fetch(fresh.url)).json()).toMatchObject({ connections: [{ connected: false }, { connected: false }] })
})

it('terminates the runtime if nginx exits or cannot start', async () => {
  const runtime = await start()
  await expect.poll(runtime.output).toMatch(/child:\d+/)
  process.kill(Number(/child:(\d+)/.exec(runtime.output())![1]), 'SIGTERM')
  expect((await runtime.exited)[0]).toBe(1)
  const failed = await start('/nonexistent-shopops-nginx')
  expect((await failed.exited)[0]).toBe(1)
})
