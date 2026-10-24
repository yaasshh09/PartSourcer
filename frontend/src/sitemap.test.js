import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { test, expect } from 'vitest'

// A page added to the router but left out here never gets crawled.
test('the sitemap lists every page a visitor can land on cold', () => {
  const xml = readFileSync(resolve('public/sitemap.xml'), 'utf8')
  const app = readFileSync(resolve('src/App.jsx'), 'utf8')
  const routes = [...app.matchAll(/path="(\/[a-z]*)"/g)].map((m) => m[1])
    // Both hold what this browser saved, so there is nothing to index.
    .filter((p) => p !== '/compare' && p !== '/watchlist')
  expect(routes.length).toBeGreaterThan(5)
  for (const r of routes) expect(xml).toContain(`<loc>https://part-sourcer.vercel.app${r}</loc>`)
  const robots = readFileSync(resolve('public/robots.txt'), 'utf8')
  expect(robots).toContain('Sitemap: https://part-sourcer.vercel.app/sitemap.xml')
})

test('the install manifest parses and every icon it names exists', () => {
  const m = JSON.parse(readFileSync(resolve('public/manifest.webmanifest'), 'utf8'))
  expect(m.start_url).toBe('/')
  for (const icon of m.icons) expect(() => readFileSync(resolve(`public${icon.src}`))).not.toThrow()
  expect(readFileSync(resolve('index.html'), 'utf8')).toContain('href="/manifest.webmanifest"')
})

test('the page says it is light only, so native controls match it on a dark system', () => {
  expect(readFileSync(resolve('index.html'), 'utf8')).toContain('<meta name="color-scheme" content="light" />')
  expect(readFileSync(resolve('src/index.css'), 'utf8')).toMatch(/:root\s*\{\s*color-scheme:\s*light;/)
})
