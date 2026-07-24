import type { BackendMethod, BackendRequest, BackendResponse } from './contracts'

const BACKEND_ORIGIN = 'http://127.0.0.1:8000'
const REQUEST_TIMEOUT_MS = 10_000

const ROUTES: ReadonlyArray<{
  readonly method: BackendMethod
  readonly pattern: RegExp
}> = [
  { method: 'GET', pattern: /^\/api\/v1\/health$/ },
  { method: 'GET', pattern: /^\/api\/v1\/readiness$/ },
  { method: 'GET', pattern: /^\/api\/v1\/models(?:\?.*)?$/ },
  { method: 'POST', pattern: /^\/api\/v1\/models\/import$/ },
  {
    method: 'POST',
    pattern: /^\/api\/v1\/models\/[A-Za-z0-9._-]+\/(?:archive|delete)$/,
  },
  { method: 'GET', pattern: /^\/api\/v1\/model-jobs\/[A-Za-z0-9._-]+$/ },
  { method: 'POST', pattern: /^\/api\/v1\/reconstruction-jobs$/ },
  {
    method: 'GET',
    pattern: /^\/api\/v1\/reconstruction-jobs\/[A-Za-z0-9._-]+$/,
  },
  { method: 'GET', pattern: /^\/api\/v1\/pipelines(?:\?.*)?$/ },
  { method: 'GET', pattern: /^\/api\/v1\/pipelines\/active$/ },
  { method: 'POST', pattern: /^\/api\/v1\/pipelines$/ },
  {
    method: 'POST',
    pattern: /^\/api\/v1\/pipelines\/[A-Za-z0-9._-]+\/(?:validate|activate)$/,
  },
  { method: 'GET', pattern: /^\/api\/v1\/runs(?:\?.*)?$/ },
  { method: 'POST', pattern: /^\/api\/v1\/runs$/ },
  { method: 'GET', pattern: /^\/api\/v1\/runs\/[A-Za-z0-9._-]+$/ },
  {
    method: 'GET',
    pattern: /^\/api\/v1\/runs\/[A-Za-z0-9._-]+\/artifacts$/,
  },
  { method: 'POST', pattern: /^\/api\/v1\/runs\/[A-Za-z0-9._-]+\/start$/ },
  { method: 'POST', pattern: /^\/api\/v1\/runs\/[A-Za-z0-9._-]+\/cancel$/ },
  { method: 'GET', pattern: /^\/api\/v1\/events(?:\?.*)?$/ },
]

export function validateBackendRequest(value: unknown): BackendRequest {
  if (!isRecord(value)) {
    throw new Error('Invalid backend request')
  }

  const method = value.method
  const path = value.path
  if ((method !== 'GET' && method !== 'POST') || typeof path !== 'string') {
    throw new Error('Invalid backend request')
  }
  if (
    path.length > 500 ||
    !ROUTES.some((route) => route.method === method && route.pattern.test(path))
  ) {
    throw new Error('Backend route is not allowed')
  }
  if (method === 'GET' && value.body !== undefined) {
    throw new Error('GET requests cannot include a body')
  }

  return { method, path, body: value.body }
}

export async function sendBackendRequest(value: unknown): Promise<BackendResponse> {
  const request = validateBackendRequest(value)
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(`${BACKEND_ORIGIN}${request.path}`, {
      method: request.method,
      headers:
        request.body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: request.body === undefined ? undefined : JSON.stringify(request.body),
      signal: controller.signal,
    })
    return {
      ok: response.ok,
      status: response.status,
      data: await readResponseBody(response),
    }
  } catch {
    return {
      ok: false,
      status: 0,
      data: { detail: 'Local backend is unavailable' },
    }
  } finally {
    clearTimeout(timeout)
  }
}

async function readResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    return null
  }
  return response.json()
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
