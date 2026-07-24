import type {
  EventBatch,
  HealthResponse,
  ModelSummary,
  ModelJobSummary,
  PipelineDraftRequest,
  PipelineSummary,
  ReadinessResponse,
  ReconstructionJobSummary,
  RunSummary,
} from './contracts'

type HttpMethod = 'GET' | 'POST'

interface DesktopResponse {
  readonly ok: boolean
  readonly status: number
  readonly data: unknown
}

interface RequestOptions {
  readonly method?: HttpMethod
  readonly body?: unknown
  readonly signal?: AbortSignal
}

export class ApiClientError extends Error {
  readonly status: number

  constructor(message: string, status = 0) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
  }
}

export class InspectionApiClient {
  constructor(private readonly origin = 'http://127.0.0.1:8000') {}

  health(signal?: AbortSignal): Promise<HealthResponse> {
    return this.request('/api/v1/health', { signal })
  }

  readiness(signal?: AbortSignal): Promise<ReadinessResponse> {
    return this.request('/api/v1/readiness', { signal })
  }

  models(signal?: AbortSignal): Promise<readonly ModelSummary[]> {
    return this.request('/api/v1/models?limit=50&offset=0', { signal })
  }

  importModel(sourcePath: string): Promise<ModelJobSummary> {
    return this.request('/api/v1/models/import', {
      method: 'POST',
      body: { source_path: sourcePath },
    })
  }

  archiveModel(modelBundleId: string): Promise<ModelJobSummary> {
    return this.request(
      `/api/v1/models/${encodeURIComponent(modelBundleId)}/archive`,
      { method: 'POST' },
    )
  }

  deleteModel(modelBundleId: string): Promise<ModelJobSummary> {
    return this.request(
      `/api/v1/models/${encodeURIComponent(modelBundleId)}/delete`,
      { method: 'POST' },
    )
  }

  modelJob(jobId: string, signal?: AbortSignal): Promise<ModelJobSummary> {
    return this.request(`/api/v1/model-jobs/${encodeURIComponent(jobId)}`, {
      signal,
    })
  }

  submitReconstruction(
    sourcePath: string,
    side: 'upper' | 'lower',
    previewSize: 3000 | 4000 | 5000,
  ): Promise<ReconstructionJobSummary> {
    return this.request('/api/v1/reconstruction-jobs', {
      method: 'POST',
      body: { source_path: sourcePath, side, preview_size: previewSize },
    })
  }

  reconstructionJob(
    jobId: string,
    signal?: AbortSignal,
  ): Promise<ReconstructionJobSummary> {
    return this.request(
      `/api/v1/reconstruction-jobs/${encodeURIComponent(jobId)}`,
      { signal },
    )
  }

  async waitForReconstructionJob(
    jobId: string,
    onProgress: (job: ReconstructionJobSummary) => void,
    signal?: AbortSignal,
  ): Promise<ReconstructionJobSummary> {
    while (true) {
      const job = await this.reconstructionJob(jobId, signal)
      onProgress(job)
      if (job.status === 'completed' || job.status === 'failed') {
        return job
      }
      await wait(500, signal)
    }
  }

  async waitForModelJob(
    jobId: string,
    signal?: AbortSignal,
  ): Promise<ModelJobSummary> {
    while (true) {
      const job = await this.modelJob(jobId, signal)
      if (job.status === 'completed' || job.status === 'failed') {
        return job
      }
      await wait(500, signal)
    }
  }

  pipelines(signal?: AbortSignal): Promise<readonly PipelineSummary[]> {
    return this.request('/api/v1/pipelines?limit=50&offset=0', { signal })
  }

  activePipeline(signal?: AbortSignal): Promise<PipelineSummary | null> {
    return this.request('/api/v1/pipelines/active', { signal })
  }

  createPipeline(request: PipelineDraftRequest): Promise<PipelineSummary> {
    return this.request('/api/v1/pipelines', {
      method: 'POST',
      body: request,
    })
  }

  validatePipeline(pipelineSnapshotId: string): Promise<PipelineSummary> {
    return this.request(
      `/api/v1/pipelines/${encodeURIComponent(pipelineSnapshotId)}/validate`,
      { method: 'POST' },
    )
  }

  activatePipeline(pipelineSnapshotId: string): Promise<PipelineSummary> {
    return this.request(
      `/api/v1/pipelines/${encodeURIComponent(pipelineSnapshotId)}/activate`,
      { method: 'POST' },
    )
  }

  runs(signal?: AbortSignal): Promise<readonly RunSummary[]> {
    return this.request('/api/v1/runs?limit=50&offset=0', { signal })
  }

  events(afterSequence: number, signal?: AbortSignal): Promise<EventBatch> {
    const query = new URLSearchParams({
      after_sequence: String(afterSequence),
      limit: '100',
    })
    return this.request(`/api/v1/events?${query}`, { signal })
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const method = options.method ?? 'GET'
    const bridge = window.productionInspection
    let response: DesktopResponse

    if (bridge) {
      response = await bridge.backend.request({
        method,
        path,
        body: options.body,
      })
    } else {
      response = await this.browserRequest(path, method, options)
    }

    if (!response.ok) {
      throw new ApiClientError(readErrorMessage(response.data), response.status)
    }
    return response.data as T
  }

  private async browserRequest(
    path: string,
    method: HttpMethod,
    options: RequestOptions,
  ): Promise<DesktopResponse> {
    try {
      const response = await fetch(`${this.origin}${path}`, {
        method,
        headers:
          options.body === undefined
            ? undefined
            : { 'Content-Type': 'application/json' },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: options.signal,
      })
      return {
        ok: response.ok,
        status: response.status,
        data: await readBody(response),
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw error
      }
      throw new ApiClientError('The local inspection service is not responding.')
    }
  }
}

async function readBody(response: Response): Promise<unknown> {
  if (!(response.headers.get('content-type') ?? '').includes('application/json')) {
    return null
  }
  return response.json()
}

function readErrorMessage(value: unknown): string {
  if (
    typeof value === 'object' &&
    value !== null &&
    'detail' in value &&
    typeof value.detail === 'string'
  ) {
    return value.detail
  }
  return 'The inspection service could not complete the request.'
}

function wait(milliseconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds)
    signal?.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer)
        reject(new DOMException('The operation was aborted.', 'AbortError'))
      },
      { once: true },
    )
  })
}

export const inspectionApi = new InspectionApiClient()
