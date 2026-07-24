export const BACKEND_REQUEST_CHANNEL = 'inspection:backend-request'

export type BackendMethod = 'GET' | 'POST'

export interface BackendRequest {
  readonly method: BackendMethod
  readonly path: string
  readonly body?: unknown
}

export interface BackendResponse {
  readonly ok: boolean
  readonly status: number
  readonly data: unknown
}

export interface DesktopBridge {
  readonly platform: NodeJS.Platform
  readonly isPackaged: boolean
  readonly backend: {
    request(request: BackendRequest): Promise<BackendResponse>
  }
}
