export const BACKEND_REQUEST_CHANNEL = 'inspection:backend-request'
export const MODEL_BUNDLE_SELECT_CHANNEL = 'inspection:select-model-bundle'
export const ACQUISITION_FOLDER_SELECT_CHANNEL = 'inspection:select-acquisition-folder'
export const CENTER_REFERENCE_SELECT_CHANNEL = 'inspection:select-center-reference'

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
  readonly models: {
    selectBundle(): Promise<string | null>
  }
  readonly acquisitions: {
    selectFolder(): Promise<string | null>
  }
  readonly centerReferences: {
    selectImage(side: 'upper' | 'lower'): Promise<string | null>
  }
}
