import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { BackendStatusProvider } from './state/BackendStatusContext'

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <BackendStatusProvider>
        <App />
      </BackendStatusProvider>
    </MemoryRouter>,
  )
}

function mockBackend(status: 'ready' | 'not_ready' = 'not_ready') {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: 'ready',
          service: 'standalone-production-inspection-backend',
          version: '0.1.0',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status,
          components: {
            database: status,
            run_commands: status,
            events: 'ready',
          },
        }),
      ),
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('application shell', () => {
  it('opens in a simple run mode without technical navigation', async () => {
    mockBackend('ready')
    renderRoute('/')

    expect(
      await screen.findByRole('heading', { name: 'Production inspection' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('navigation', { name: 'Configuration navigation' }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Configuration' })).toBeInTheDocument()
    expect(await screen.findByText('Core services ready')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start production run' })).toBeDisabled()
  })

  it('keeps configuration in a separate technical workspace', async () => {
    mockBackend()
    renderRoute('/configuration/setup')

    expect(
      screen.getByRole('heading', { name: 'Setup & validation' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Configuration navigation' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Return to Run Mode' })).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Production inspection' }),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Protected technical workspace')).toBeInTheDocument()
    expect(screen.getByText('Production-safe by design')).toBeInTheDocument()
  })

  it('shows saved cycles as previous inspections inside run mode', () => {
    mockBackend()
    renderRoute('/run/history')

    expect(
      screen.getByRole('heading', { name: 'Previous inspections' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Current run' })).toBeInTheDocument()
    expect(screen.getByText(/one complete acquisition cycle of 16 images/i)).toBeInTheDocument()
  })
})
