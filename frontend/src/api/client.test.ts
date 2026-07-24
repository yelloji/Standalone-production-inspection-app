import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError, InspectionApiClient } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
  Object.defineProperty(window, 'productionInspection', {
    configurable: true,
    value: undefined,
  })
})

describe('InspectionApiClient', () => {
  it('uses the isolated desktop bridge when available', async () => {
    const request = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      data: { status: 'ready', service: 'backend', version: '0.1.0' },
    })
    Object.defineProperty(window, 'productionInspection', {
      configurable: true,
      value: { platform: 'win32', isPackaged: true, backend: { request } },
    })

    await new InspectionApiClient().health()

    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      path: '/api/v1/health',
      body: undefined,
    })
  })

  it('returns a stable typed error for unavailable browser transport', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network detail')))

    await expect(new InspectionApiClient().health()).rejects.toEqual(
      expect.objectContaining<ApiClientError>({
        name: 'ApiClientError',
        message: 'The local inspection service is not responding.',
        status: 0,
      }),
    )
  })
})
