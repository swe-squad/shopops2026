import { spawn } from 'node:child_process'
import { createServer } from 'node:http'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createConnectorHandler } from './connectors.ts'

// One owner for both processes: nginx must not keep serving a dead mock instance.
export function startRuntime(command = '/docker-entrypoint.sh', args = ['nginx', '-g', 'daemon off;'], port = 3001) {
  const server = createServer(createConnectorHandler())
  let nginx: ReturnType<typeof spawn> | undefined
  let stopping = false
  const stop = (code: number) => {
    if (stopping) return
    stopping = true
    process.exitCode = code
    server.close()
    server.closeAllConnections()
    nginx?.kill('SIGTERM')
    // Bound shutdown if nginx does not respond; the timer is not an extra live handle.
    setTimeout(() => { nginx?.kill('SIGKILL'); process.exit(code) }, 5000).unref()
  }
  process.once('SIGTERM', () => stop(0))
  process.once('SIGINT', () => stop(0))
  server.on('error', () => { console.error('Mock connector server failed.'); stop(1) })
  server.listen(port, '127.0.0.1', () => {
    nginx = spawn(command, args, { stdio: 'inherit' })
    nginx.on('error', () => { console.error('Could not start nginx.'); stop(1) })
    nginx.on('exit', () => { if (!stopping) stop(1) })
  })
  return server
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) startRuntime()
