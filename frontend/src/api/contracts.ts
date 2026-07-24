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
  readonly referenced_by_pipelines: boolean
  readonly can_archive: boolean
  readonly can_delete: boolean
}

export interface ModelJobSummary {
  readonly job_id: string
  readonly action: 'import' | 'archive' | 'delete'
  readonly status: 'queued' | 'running' | 'completed' | 'failed'
  readonly model_bundle_id: string | null
  readonly message: string | null
}

export interface ReconstructionJobSummary {
  readonly job_id: string
  readonly status: 'queued' | 'running' | 'completed' | 'failed'
  readonly stage: string
  readonly progress_current: number
  readonly progress_total: number
  readonly acquisition_id: string | null
  readonly production_approved: boolean | null
  readonly validation_median_px: number | null
  readonly validation_p95_px: number | null
  readonly validation_maximum_px: number | null
  readonly passed_join_count: number | null
  readonly total_join_count: number | null
  readonly preview_url: string | null
  readonly preview_relative_path: string | null
  readonly report_relative_path: string | null
  readonly preview_width: number | null
  readonly preview_height: number | null
  readonly center_completion_applied: boolean | null
  readonly center_profile_id: string | null
  readonly center_rotation_degrees: number | null
  readonly center_fill_pixels: number | null
  readonly message: string | null
}

export interface CenterReferenceSummary {
  readonly side: 'upper' | 'lower'
  readonly profile_id: string
  readonly installed: boolean
  readonly relative_path: string
  readonly sha256: string | null
  readonly message: string
}

export interface PipelineSummary {
  readonly pipeline_snapshot_id: string
  readonly pipeline_id: string
  readonly revision: number
  readonly display_name: string
  readonly state: string
  readonly model_bundle_id: string | null
  readonly acquisition_mode: 'manual_folder' | 'automatic_folder'
  readonly expected_frame_count: number
  readonly filename_template: string | null
  readonly reconstruction_enabled: boolean
  readonly inference_enabled: boolean
  readonly inference_mode: string | null
  readonly can_validate: boolean
  readonly can_activate: boolean
  readonly sha256: string
  readonly created_at: string
}

export type AcquisitionSource = 'offline' | 'online'
export type AcquisitionMode = 'manual_folder' | 'automatic_folder'
export type DiscSide = 'upper' | 'lower' | 'not_applicable'
export type InferenceMode = 'direct' | 'sahi'

export interface PipelineDraftRequest {
  readonly pipeline_id: string
  readonly display_name: string
  readonly model_bundle_id: string | null
  readonly acquisition: {
    readonly source: AcquisitionSource
    readonly expected_frame_count: number
    readonly ordered: boolean
    readonly side: DiscSide
    readonly mode: AcquisitionMode
    readonly automatic: {
      readonly filename_template: string
      readonly position_width: number
      readonly stable_for_milliseconds: number
      readonly incomplete_cycle_timeout_seconds: number
    } | null
  }
  readonly inference:
    | {
        readonly enabled: false
        readonly mode: null
        readonly confidence_threshold: null
        readonly sahi: null
      }
    | {
        readonly enabled: true
        readonly mode: InferenceMode
        readonly confidence_threshold: number
        readonly sahi: {
          readonly slice_width: number
          readonly slice_height: number
          readonly overlap_width_ratio: number
          readonly overlap_height_ratio: number
          readonly batch_size: number
        } | null
      }
  readonly reconstruction:
    | {
        readonly enabled: false
        readonly segment_count: null
        readonly degrees_per_segment: null
      }
    | {
        readonly enabled: true
        readonly segment_count: number
        readonly degrees_per_segment: number
      }
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
