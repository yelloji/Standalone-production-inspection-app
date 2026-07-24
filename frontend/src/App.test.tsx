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

function mockBackend(
  status: 'ready' | 'not_ready' = 'not_ready',
  activePipeline: unknown = null,
) {
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url.endsWith('/api/v1/health')) {
      return Promise.resolve(
        jsonResponse({
          status: 'ready',
          service: 'standalone-production-inspection-backend',
          version: '0.1.0',
        }),
      )
    }
    if (url.endsWith('/api/v1/readiness')) {
      return Promise.resolve(
        jsonResponse({
          status,
          components: {
            database: status,
            run_commands: status,
            events: 'ready',
          },
        }),
      )
    }
    if (url.endsWith('/api/v1/pipelines/active')) {
      return Promise.resolve(jsonResponse(activePipeline))
    }
    return Promise.resolve(jsonResponse([]))
  }))
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
    expect(await screen.findByText('Setup required')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start production run' })).toBeDisabled()
  })

  it('keeps configuration in a separate technical workspace', async () => {
    mockBackend()
    renderRoute('/configuration/pipelines')

    expect(
      await screen.findByRole('heading', { name: 'Production pipeline' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Configuration navigation' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Return to Run Mode' })).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Production inspection' }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Model Library/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Offline Validation/i })).toBeInTheDocument()
    expect(screen.getByText('Reconstruction')).toBeInTheDocument()
    expect(screen.getByText('AI inference')).toBeInTheDocument()
    expect(screen.getByText('Automatic acquisition intake')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /Filename template/i })).toHaveValue(
      '{cycle}_{position}.jpg',
    )
  })

  it('shows automatic acquisition progress only in run mode', async () => {
    mockBackend('ready', {
      pipeline_snapshot_id: 'brake-disc-r2',
      pipeline_id: 'brake-disc',
      revision: 2,
      display_name: 'Brake Disc Inspection',
      state: 'active',
      model_bundle_id: null,
      acquisition_mode: 'automatic_folder',
      expected_frame_count: 16,
      filename_template: '{cycle}_{position}.jpg',
      reconstruction_enabled: true,
      inference_enabled: false,
      inference_mode: null,
      can_validate: false,
      can_activate: false,
      sha256: 'a'.repeat(64),
      created_at: '2026-07-24T08:00:00Z',
    })
    renderRoute('/run')

    expect(
      await screen.findByRole('heading', { name: 'Waiting for acquisition' }),
    ).toBeInTheDocument()
    expect(screen.getByText('0 / 16 received')).toBeInTheDocument()
    expect(screen.getByText(/matching \{cycle\}_\{position\}\.jpg/i)).toBeInTheDocument()
    expect(
      screen.queryByRole('textbox', { name: /Filename template/i }),
    ).not.toBeInTheDocument()
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
