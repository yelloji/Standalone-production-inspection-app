export type ReadinessState = 'ready' | 'not_ready'

export interface HealthResponse {
  readonly status: 'ready'
  readonly service: string
  readonly version: string
}

export interface ReadinessResponse {
  readonly status: ReadinessState
  readonly components: Readonly<Record<string, ReadinessState>>
}

export interface ModelSummary {
  readonly model_bundle_id: string
  readonly display_name: string
  readonly model_version: string
  readonly state: string
  readonly sha256: string
  readonly created_at: string
}

export interface PipelineSummary {
  readonly pipeline_snapshot_id: string
  readonly pipeline_id: string
  readonly revision: number
  readonly display_name: string
  readonly state: string
  readonly model_bundle_id: string
  readonly sha256: string
  readonly created_at: string
}

export interface RunSummary {
  readonly run_id: string
  readonly acquisition_id: string
  readonly pipeline_snapshot_id: string
  readonly source: string
  readonly side: string
  readonly status: string
  readonly failure_code: string | null
  readonly created_at: string
  readonly started_at: string | null
  readonly finished_at: string | null
}

export interface EventBatch {
  readonly events: readonly RunEvent[]
  readonly latest_sequence: number
  readonly gap_detected: boolean
}

export interface RunEvent {
  readonly sequence: number
  readonly occurred_at: string
  readonly event_type: string
  readonly run_id: string | null
  readonly stage: string | null
  readonly progress_current: number | null
  readonly progress_total: number | null
  readonly message: string | null
}
