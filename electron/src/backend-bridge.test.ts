import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, it } from 'node:test'

import { validateBackendRequest } from './backend-bridge'

describe('backend bridge allow-list', () => {
  it('accepts versioned inspection API routes', () => {
    assert.deepEqual(
      validateBackendRequest({
        method: 'GET',
        path: '/api/v1/events?after_sequence=12&limit=50',
      }),
      {
        method: 'GET',
        path: '/api/v1/events?after_sequence=12&limit=50',
        body: undefined,
      },
    )
    assert.deepEqual(
      validateBackendRequest({
        method: 'POST',
        path: '/api/v1/models/crack-v1/archive',
      }),
      {
        method: 'POST',
        path: '/api/v1/models/crack-v1/archive',
        body: undefined,
      },
    )
    assert.deepEqual(
      validateBackendRequest({
        method: 'POST',
        path: '/api/v1/pipelines/brake-disc-r2/activate',
      }),
      {
        method: 'POST',
        path: '/api/v1/pipelines/brake-disc-r2/activate',
        body: undefined,
      },
    )
    assert.deepEqual(
      validateBackendRequest({
        method: 'GET',
        path: '/api/v1/reconstruction-jobs/job-001',
      }),
      {
        method: 'GET',
        path: '/api/v1/reconstruction-jobs/job-001',
        body: undefined,
      },
    )
    assert.deepEqual(
      validateBackendRequest({
        method: 'POST',
        path: '/api/v1/center-references/import',
      }),
      {
        method: 'POST',
        path: '/api/v1/center-references/import',
        body: undefined,
      },
    )
    assert.deepEqual(
      validateBackendRequest({
        method: 'POST',
        path: '/api/v1/runs/run-001/start',
      }),
      {
        method: 'POST',
        path: '/api/v1/runs/run-001/start',
        body: undefined,
      },
    )
  })

  it('rejects arbitrary URLs and disallowed methods', () => {
    assert.throws(
      () =>
        validateBackendRequest({
          method: 'GET',
          path: 'https://example.com/api/v1/health',
        }),
      /not allowed/,
    )
    assert.throws(
      () =>
        validateBackendRequest({
          method: 'DELETE',
          path: '/api/v1/runs/run-001',
        }),
      /Invalid backend request/,
    )
  })
})

describe('sandboxed preload build', () => {
  it('does not require local modules at runtime', () => {
    const compiledPreload = readFileSync(path.join(__dirname, 'preload.js'), 'utf8')

    assert.doesNotMatch(compiledPreload, /require\(["']\.\//)
  })
})
