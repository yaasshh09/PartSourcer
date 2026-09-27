import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, afterEach, test, expect } from 'vitest'
import BrowsePage from './BrowsePage.jsx'
import * as api from '../api.js'

afterEach(() => { vi.restoreAllMocks() })

const wrap = () => render(<MemoryRouter><BrowsePage /></MemoryRouter>)

test('shows a card per category linking to its page', async () => {
  vi.spyOn(api, 'getCategories').mockResolvedValue({ categories: [
    { slug: 'resistors', label: 'Resistors', note: null, filters: [
      { name: 'package', label: 'Package', kind: 'choice', choices: ['0603'] },
      { name: 'resistance', label: 'Resistance', kind: 'number', example: '10k' }] },
    { slug: 'leds', label: 'LEDs', note: null, filters: [] },
  ] })
  wrap()
  expect(await screen.findByRole('link', { name: /Resistors/ })).toHaveAttribute('href', '/browse/resistors')
  expect(screen.getByRole('link', { name: /LEDs/ })).toHaveAttribute('href', '/browse/leds')
  expect(screen.getByText(/package, resistance/)).toBeInTheDocument()
})

test('keeps acronyms intact in the filter summary', async () => {
  vi.spyOn(api, 'getCategories').mockResolvedValue({ categories: [
    { slug: 'mosfets', label: 'MOSFETs', note: null, filters: [
      { name: 'package', label: 'Package', kind: 'choice', choices: ['SOT-23'] },
      { name: 'min_vds', label: 'Min Vds', kind: 'number', example: '30' },
      { name: 'min_id', label: 'Min Id', kind: 'number', example: '2' }] },
  ] })
  wrap()
  expect(await screen.findByText('Filter by package, min Vds, min Id')).toBeInTheDocument()
})

test('says so when the categories cannot load', async () => {
  vi.spyOn(api, 'getCategories').mockRejectedValue(new api.ApiError(503, 'jlcsearch unreachable'))
  wrap()
  expect(await screen.findByText(/jlcsearch unreachable/)).toBeInTheDocument()
})
