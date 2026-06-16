import { describe, expect, test } from 'bun:test'

import { getResumeProgress } from './documentResume'

describe('getResumeProgress (AC-008 resume indicator)', () => {
  test('returns progress for a failed doc with a partial checkpoint', () => {
    const result = getResumeProgress({
      status: 'failed',
      chunks_count: 10,
      metadata: { pipeline_phase: 'extraction', extracted_chunks: 6 }
    })
    expect(result).toEqual({ phase: 'extraction', extracted: 6, total: 10 })
  })

  test('returns progress for an in-flight processing doc', () => {
    const result = getResumeProgress({
      status: 'processing',
      chunks_count: 8,
      metadata: { pipeline_phase: 'extraction', extracted_chunks: 3 }
    })
    expect(result).toEqual({ phase: 'extraction', extracted: 3, total: 8 })
  })

  test('returns null for a processed doc (no resume indicator)', () => {
    expect(
      getResumeProgress({
        status: 'processed',
        chunks_count: 10,
        metadata: { pipeline_phase: 'completed', extracted_chunks: 10 }
      })
    ).toBeNull()
  })

  test('returns null when fully extracted (nothing to resume)', () => {
    expect(
      getResumeProgress({
        status: 'failed',
        chunks_count: 10,
        metadata: { pipeline_phase: 'merge', extracted_chunks: 10 }
      })
    ).toBeNull()
  })

  test('returns null when metadata lacks extracted_chunks (legacy doc)', () => {
    expect(
      getResumeProgress({ status: 'failed', chunks_count: 10, metadata: {} })
    ).toBeNull()
    expect(getResumeProgress({ status: 'failed', chunks_count: 10 })).toBeNull()
  })

  test('defaults phase to "extraction" when pipeline_phase missing', () => {
    const result = getResumeProgress({
      status: 'failed',
      chunks_count: 5,
      metadata: { extracted_chunks: 2 }
    })
    expect(result).toEqual({ phase: 'extraction', extracted: 2, total: 5 })
  })
})
