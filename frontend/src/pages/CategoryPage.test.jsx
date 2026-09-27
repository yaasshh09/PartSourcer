import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import CategoryPage from './CategoryPage.jsx'
import { CompareProvider } from '../compare.jsx'
import * as api from '../api.js'

const SCHEMA = { categories: [
  { slug: 'resistors', label: 'Resistors', note: null, filters: [
    { name: 'package', label: 'Package', kind: 'choice', unit: null, choices: ['0402', '0603'], example: null },
    { name: 'resistance', label: 'Resistance', kind: 'number', unit: 'ohm', choices: null, example: '10k' },
    { name: 'basic', label: 'Basic parts only', kind: 'bool', unit: null, choices: null, example: null },
  ] },
  { slug: 'diodes', label: 'Diodes', note: 'The source data does not type diodes, so filter by package and check the specs.',
    filters: [{ name: 'package', label: 'Package', kind: 'choice', unit: null, choices: ['SOD-123'], example: null }] },
] }

function row(over = {}) {
  return { mpn: '0603WAF1002T5E', mpn_key: '0603WAF1002T5E', lcsc: 'C25804', package: '0603',
    stock: 37165617, specs: [['Resistance', '10 kOhm'], ['Tolerance', null]], ...over }
}

function answer(over = {}) {
  return { category: 'resistors', results: [row()], count: 1, capped: false,
    as_of: '2026-09-27T08:00:00Z', ...over }
}

let where
function Where() { where = useLocation(); return null }

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/browse/:slug" element={<><CategoryPage /><Where /></>} /></Routes>
    </MemoryRouter>)
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'getCategories').mockResolvedValue(SCHEMA)
})
afterEach(() => { vi.restoreAllMocks() })

test('builds the form from the schema and lists parts', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer())
  renderAt('/browse/resistors')
  expect(await screen.findByText('0603WAF1002T5E')).toBeInTheDocument()
  expect(screen.getByLabelText('Package')).toBeInTheDocument()
  expect(screen.getByLabelText('Resistance')).toHaveAttribute('placeholder', 'e.g. 10k')
  expect(screen.getByLabelText('Basic parts only')).toHaveAttribute('type', 'checkbox')
  expect(api.browse).toHaveBeenCalledWith('resistors', {})
})

test('each part links to its part page through encodeKey', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer({ results: [row({ mpn: 'LM358P/NOPB', mpn_key: 'LM358P/NOPB' })] }))
  renderAt('/browse/resistors')
  expect(await screen.findByRole('link', { name: 'LM358P/NOPB' })).toHaveAttribute('href', '/part/LM358P/NOPB')
})

test('the URL drives the first request and fills the form', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer())
  renderAt('/browse/resistors?package=0603&resistance=4k7')
  await screen.findByText('0603WAF1002T5E')
  expect(api.browse).toHaveBeenCalledWith('resistors', { package: '0603', resistance: '4k7' })
  expect(screen.getByLabelText('Package')).toHaveValue('0603')
  expect(screen.getByLabelText('Resistance')).toHaveValue('4k7')
})

test('applying the form writes the filters into the URL', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer())
  renderAt('/browse/resistors')
  await screen.findByText('0603WAF1002T5E')
  fireEvent.change(screen.getByLabelText('Package'), { target: { value: '0402' } })
  fireEvent.change(screen.getByLabelText('Resistance'), { target: { value: ' 10k ' } })
  fireEvent.click(screen.getByLabelText('Basic parts only'))
  fireEvent.click(screen.getByRole('button', { name: 'APPLY' }))
  await waitFor(() => expect(api.browse).toHaveBeenLastCalledWith(
    'resistors', { package: '0402', resistance: '10k', basic: 'true' }))
  expect(new URLSearchParams(where.search).get('resistance')).toBe('10k')
})

test('a capped answer says it is from the top 100 by stock', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer({ capped: true }))
  renderAt('/browse/resistors')
  expect(await screen.findByText('1 PARTS FROM THE TOP 100 BY STOCK')).toBeInTheDocument()
  expect(screen.getByText(/LCSC snapshot, read Sep 27, 2026/)).toBeInTheDocument()
})

test('an uncapped answer gives a plain count', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer())
  renderAt('/browse/resistors')
  expect(await screen.findByText('1 PARTS')).toBeInTheDocument()
})

test('a missing spec reads not listed', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer())
  renderAt('/browse/resistors')
  expect(await screen.findByText('not listed')).toBeInTheDocument()
})

test('two LCSC codes for one MPN render as two rows', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer({ count: 2, results: [
    row({ mpn: '1N4148W', mpn_key: '1N4148W', lcsc: 'C1' }),
    row({ mpn: '1N4148W', mpn_key: '1N4148W', lcsc: 'C2' }),
  ] }))
  renderAt('/browse/resistors')
  await waitFor(() => expect(screen.getAllByRole('link', { name: '1N4148W' })).toHaveLength(2))
})

test('a refused filter shows the reason and keeps the form', async () => {
  vi.spyOn(api, 'browse').mockRejectedValue(new api.ApiError(422, "'0604' is not a package we list for Resistors."))
  renderAt('/browse/resistors?package=0604')
  expect(await screen.findByText("'0604' is not a package we list for Resistors.")).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'APPLY' })).toBeInTheDocument()
})

test('no matches gets an honest empty state', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer({ results: [], count: 0 }))
  renderAt('/browse/resistors')
  expect(await screen.findByText(/No parts match/)).toBeInTheDocument()
})

test('a category note is shown', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer({ category: 'diodes' }))
  renderAt('/browse/diodes')
  expect(await screen.findByText(/does not type diodes/)).toBeInTheDocument()
})

test('an unknown category never asks for parts', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer())
  renderAt('/browse/rockets')
  expect(await screen.findByText('NO SUCH CATEGORY')).toBeInTheDocument()
  expect(api.browse).not.toHaveBeenCalled()
})

test('never shows a price or calls the data live', async () => {
  vi.spyOn(api, 'browse').mockResolvedValue(answer({ capped: true }))
  const { container } = renderAt('/browse/resistors')
  await screen.findByText('0603WAF1002T5E')
  expect(container.textContent).not.toMatch(/\$|price|live/i)
})

test('a browse row can be pinned for comparison', async () => {
  localStorage.clear()
  vi.spyOn(api, 'browse').mockResolvedValue(answer())
  render(
    <MemoryRouter initialEntries={['/browse/resistors']}>
      <CompareProvider>
        <Routes><Route path="/browse/:slug" element={<CategoryPage />} /></Routes>
      </CompareProvider>
    </MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '+ Compare' }))
  expect(JSON.parse(localStorage.getItem('ps-compare'))).toEqual(['0603WAF1002T5E'])
  localStorage.clear()
})
