import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
export const ROOT = path.resolve(__dirname, '..')

const DEFAULTS = {
  port: 8787,
  prompter: { defaultSpeed: 45, defaultFontSize: 48, mirror: false },
}

export function readConfig() {
  const file = path.join(ROOT, 'cordis.yml')
  try {
    const parsed = parse(fs.readFileSync(file, 'utf8')) || {}
    return {
      ...DEFAULTS,
      ...parsed,
      prompter: { ...DEFAULTS.prompter, ...(parsed.prompter || {}) },
    }
  } catch {
    return DEFAULTS
  }
}
