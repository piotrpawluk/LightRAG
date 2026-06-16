/**
 * E2E: TC-003 — Reprocess from scratch from the Document Manager.
 * Spec: specs/resumable-ingestion.md (TC-003); UX: specs/ux/resumable-ingestion-ux.md
 *
 * STATUS: SCAFFOLD — not yet runnable in CI. The project has no Playwright harness
 * installed yet (see docs/plans/resumable-ingestion-plan.md TASK-021a). To run:
 *
 *   cd lightrag_webui && bun add -d @playwright/test && bunx playwright install chromium
 *   # build + serve the WebUI against a running LightRAG server, then:
 *   bunx playwright test ../tests/e2e/resumable-ingestion.spec.ts
 *
 * Pre-req fixtures: a LightRAG server seeded with one FAILED document that has a
 * partial extraction checkpoint (e.g. metadata.extracted_chunks < chunks_count).
 *
 * Screenshot checkpoints (per quality-gates screenshot protocol):
 *   tests/screenshots/resumable-ingestion/step-01-resume-indicator.png
 *   tests/screenshots/resumable-ingestion/step-02-reprocess-from-scratch-confirm.png
 *   tests/screenshots/resumable-ingestion/step-03-processed.png
 */
import { test, expect } from '@playwright/test'

const BASE_URL = process.env.LIGHTRAG_WEBUI_URL ?? 'http://localhost:9621'
const SHOTS = 'tests/screenshots/resumable-ingestion'

test.describe('TC-003: Reprocess from scratch', () => {
  test('failed doc shows resume indicator, reprocess-from-scratch restarts it', async ({
    page
  }) => {
    // Step 1: open Documents view; a failed doc shows an "extraction k/total" indicator.
    await page.goto(`${BASE_URL}/documents`)
    const failedRow = page.getByRole('row').filter({ hasText: 'Failed' }).first()
    await expect(failedRow).toContainText(/extraction \d+\/\d+/)
    await page.screenshot({ path: `${SHOTS}/step-01-resume-indicator.png`, fullPage: true })

    // Step 2: select the row, open "Reprocess from scratch", confirm dialog appears.
    await failedRow.getByRole('checkbox').check()
    await page.getByRole('button', { name: /Reprocess from scratch/i }).click()
    await expect(page.getByText(/Saved progress will be lost/i)).toBeVisible()
    await page.screenshot({
      path: `${SHOTS}/step-02-reprocess-from-scratch-confirm.png`,
      fullPage: true
    })

    // Step 3: confirm; the document reprocesses and reaches Completed.
    await page.getByPlaceholder(/Type yes to confirm/i).fill('yes')
    await page.getByRole('button', { name: /^Reprocess$/ }).click()
    await expect(failedRow).toContainText('Completed', { timeout: 60_000 })
    await page.screenshot({ path: `${SHOTS}/step-03-processed.png`, fullPage: true })
  })
})
