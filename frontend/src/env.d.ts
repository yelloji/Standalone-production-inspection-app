interface BackendBridgeRequest {
  readonly method: 'GET' | 'POST'
  readonly path: string
  readonly body?: unknown
}

interface ProductionInspectionBridge {
  readonly platform: string
  readonly isPackaged: boolean
  readonly backend: {
    request(request: BackendBridgeRequest): Promise<{
      readonly ok: boolean
      readonly status: number
      readonly data: unknown
    }>
  }
  readonly models: {
    selectBundle(): Promise<string | null>
  }
  readonly acquisitions: {
    selectFolder(): Promise<string | null>
  }
}

interface Window {
  readonly productionInspection?: ProductionInspectionBridge
}
