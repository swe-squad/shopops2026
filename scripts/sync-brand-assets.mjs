import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve, dirname } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const check = process.argv.includes('--check')
const services = ['shopops-workspace', 'shopops-web', 'shopops-chat']
const assets = {
  'tokens/brand-tokens.css': 'brand-tokens.css',
  'logos/mark-primary.svg': 'mark-primary.svg',
  'app/favicon.ico': 'favicon.ico',
  'app/app-icon-180.png': 'app-icon-180.png',
}
let drift = false

const tokens = JSON.parse(await readFile(resolve(root, 'docs/brand/assets/tokens/brand-tokens.json'), 'utf8'))
const tokenCss = await readFile(resolve(root, 'docs/brand/assets/tokens/brand-tokens.css'), 'utf8')
const cssValues = new Map([...tokenCss.matchAll(/(--shopops-[\w-]+)\s*:\s*([^;]+);/g)].map(match => [match[1], match[2].trim()]))
for (const [group, entries] of Object.entries(tokens)) {
  for (const [name, value] of Object.entries(entries)) {
    const variable = `--shopops-${group}-${name.replaceAll('_', '-')}`
    if (cssValues.get(variable) !== value) throw new Error(`Canonical JSON/CSS token mismatch: ${variable}`)
    cssValues.delete(variable)
  }
}
if (cssValues.size) throw new Error(`CSS tokens missing from canonical JSON: ${[...cssValues.keys()].join(', ')}`)

// Vendor static assets, not application code. Each service stays independently buildable.
for (const service of services) {
  for (const [source, filename] of Object.entries(assets)) {
    const canonical = await readFile(resolve(root, 'docs/brand/assets', source))
    const target = resolve(root, 'services', service, 'public/brand', filename)
    if (check) {
      const current = await readFile(target).catch(error => {
        if (error.code !== 'ENOENT') throw error
        return null
      })
      if (!current?.equals(canonical)) {
        console.error(`Brand asset drift: services/${service}/public/brand/${filename}`)
        drift = true
      }
    } else {
      await mkdir(dirname(target), { recursive: true })
      await writeFile(target, canonical)
    }
  }
}

if (drift) {
  console.error('Run node scripts/sync-brand-assets.mjs after editing the canonical brand kit.')
  process.exitCode = 1
} else {
  console.log(`Brand assets ${check ? 'verified' : 'synced'} for ${services.length} independent clients.`)
}
