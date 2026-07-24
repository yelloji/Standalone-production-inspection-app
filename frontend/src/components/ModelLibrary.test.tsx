import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ModelLibrary } from './ModelLibrary'

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  Object.defineProperty(window, 'productionInspection', {
    configurable: true,
    value: undefined,
  })
})

describe('ModelLibrary', () => {
  it('selects, validates, and displays an imported desktop model bundle', async () => {
    const selectBundle = vi.fn().mockResolvedValue('D:\\imports\\crack-model.zip')
    Object.defineProperty(window, 'productionInspection', {
      configurable: true,
      value: {
        platform: 'win32',
        isPackaged: false,
        backend: {
          request: vi
            .fn()
            .mockResolvedValueOnce({ ok: true, status: 200, data: [] })
            .mockResolvedValueOnce({
              ok: true,
              status: 202,
              data: {
                job_id: 'job-1',
                action: 'import',
                status: 'running',
                model_bundle_id: null,
                message: null,
              },
            })
            .mockResolvedValueOnce({
              ok: true,
              status: 200,
              data: {
                job_id: 'job-1',
                action: 'import',
                status: 'completed',
                model_bundle_id: 'crack-v1',
                message: null,
              },
            })
            .mockResolvedValueOnce({
              ok: true,
              status: 200,
              data: [
                {
                  model_bundle_id: 'crack-v1',
                  display_name: 'Crack Detection',
                  model_version: '1.0.0',
                  state: 'valid',
                  sha256: 'a'.repeat(64),
                  created_at: '2026-07-24T08:00:00Z',
                  referenced_by_pipelines: false,
                  can_archive: true,
                  can_delete: false,
                },
              ],
            }),
        },
        models: { selectBundle },
      },
    })

    render(<ModelLibrary />)
    await screen.findByText('No models imported')
    fireEvent.click(screen.getByRole('button', { name: 'Import model bundle' }))

    expect(await screen.findByText('Crack Detection')).toBeInTheDocument()
    expect(screen.getByText('Model bundle imported and validated.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archive' })).toBeEnabled()
    expect(selectBundle).toHaveBeenCalledOnce()
  })

  it('explains that browser-only mode cannot open native model bundles', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])))
    render(<ModelLibrary />)
    await screen.findByText('No models imported')

    fireEvent.click(screen.getByRole('button', { name: 'Import model bundle' }))

    await waitFor(() =>
      expect(
        screen.getByRole('alert'),
      ).toHaveTextContent('available in the desktop application'),
    )
  })
})
