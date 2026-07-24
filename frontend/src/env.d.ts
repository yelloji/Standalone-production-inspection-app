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
}

interface Window {
  readonly productionInspection?: ProductionInspectionBridge
}
