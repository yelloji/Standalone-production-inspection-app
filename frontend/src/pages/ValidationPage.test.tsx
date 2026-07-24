import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ValidationPage } from './ValidationPage'

const runningJob = {
  job_id: 'reconstruction-1',
  status: 'running',
  stage: 'registering',
  progress_current: 9,
  progress_total: 16,
  acquisition_id: null,
  production_approved: null,
  validation_median_px: null,
  validation_p95_px: null,
  validation_maximum_px: null,
  passed_join_count: null,
  total_join_count: null,
  preview_url: null,
  preview_relative_path: null,
  report_relative_path: null,
  preview_width: null,
  preview_height: null,
  message: null,
} as const

const completedJob = {
  ...runningJob,
  status: 'completed',
  stage: 'completed',
  progress_current: 1,
  progress_total: 1,
  acquisition_id: 'offline-1',
  production_approved: false,
  validation_median_px: 0.47,
  validation_p95_px: 0.84,
  validation_maximum_px: 2.03,
  passed_join_count: 11,
  total_join_count: 16,
  preview_url: '/api/v1/reconstruction-jobs/reconstruction-1/preview',
  preview_relative_path: 'completed/offline-1/reconstructed-preview.png',
  report_relative_path: 'completed/offline-1/reconstruction-report.json',
  preview_width: 5000,
  preview_height: 5000,
} as const

afterEach(() => {
  cleanup()
  window.sessionStorage.clear()
  Object.defineProperty(window, 'productionInspection', {
    configurable: true,
    value: undefined,
  })
})

describe('ValidationPage reconstruction continuity', () => {
  it('restores and resumes the same background job after navigation', async () => {
    window.sessionStorage.setItem(
      'inspection.reconstruction.session.v1',
      JSON.stringify({
        jobId: 'reconstruction-1',
        sourcePath: 'V:\\acquisitions\\upper',
        side: 'upper',
        previewSize: 5000,
      }),
    )
    const request = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      data: runningJob,
    })
    Object.defineProperty(window, 'productionInspection', {
      configurable: true,
      value: {
        platform: 'win32',
        isPackaged: false,
        backend: { request },
        models: { selectBundle: vi.fn() },
        acquisitions: { selectFolder: vi.fn() },
      },
    })

    const first = render(<ValidationPage />)
    expect(await screen.findByText('Aligning neighboring frames')).toBeInTheDocument()
    expect(screen.getByLabelText('Disc side')).toHaveValue('upper')
    expect(screen.getByLabelText('Saved image size')).toHaveValue('5000')
    expect(screen.getByText('V:\\acquisitions\\upper')).toBeInTheDocument()
    first.unmount()

    request.mockResolvedValue({
      ok: true,
      status: 200,
      data: completedJob,
    })
    render(<ValidationPage />)

    expect(await screen.findByRole('heading', { name: 'Review preview' })).toBeInTheDocument()
    expect(screen.getByText('11 / 16')).toBeInTheDocument()
    expect(screen.getByText(/5000 × 5000 px/)).toBeInTheDocument()
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith({
        method: 'GET',
        path: '/api/v1/reconstruction-jobs/reconstruction-1',
        body: undefined,
      }),
    )
  })
})
