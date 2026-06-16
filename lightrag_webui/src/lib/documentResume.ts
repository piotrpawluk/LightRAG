import type { DocStatusResponse } from '@/api/lightrag'

export type ResumeProgress = {
  phase: string
  extracted: number
  total: number
}

/**
 * Derive resume progress for a document's status cell.
 *
 * Returns a {phase, extracted, total} object only when a document is in-flight
 * (processing) or failed AND has a partial extraction checkpoint
 * (extracted_chunks < chunks_count). Otherwise returns null — processed/pending
 * rows and fully-extracted rows show no resume indicator.
 */
export function getResumeProgress(
  doc: Pick<DocStatusResponse, 'status' | 'chunks_count' | 'metadata'>
): ResumeProgress | null {
  if (doc.status !== 'processing' && doc.status !== 'failed') return null

  const meta = doc.metadata
  if (!meta) return null

  const extracted = meta.extracted_chunks
  const total = doc.chunks_count

  if (typeof extracted !== 'number' || typeof total !== 'number' || total <= 0) {
    return null
  }
  if (extracted >= total) return null // nothing left to resume

  const phase = typeof meta.pipeline_phase === 'string' ? meta.pipeline_phase : 'extraction'
  return { phase, extracted, total }
}
