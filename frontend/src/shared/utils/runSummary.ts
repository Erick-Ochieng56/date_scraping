import type { AISearchJob, CrawlRun, ScrapeRun } from '@/shared/api/types'

const AI_SEARCH_IN_PROGRESS = new Set(['pending', 'generating', 'searching'])

/** Plain-language "what happened" sentence for a site check — reused anywhere runs appear. */
export function summarizeScrapeRun(run: ScrapeRun): string {
  if (run.status === 'running') return `Checking ${run.target_name}…`
  if (run.status === 'failed') {
    return `Check of ${run.target_name} didn't finish${run.error_text ? ` — ${run.error_text}` : ' — it will retry automatically.'}`
  }
  return run.created_leads > 0
    ? `Checked ${run.target_name} and found ${run.created_leads} new prospect${run.created_leads === 1 ? '' : 's'}.`
    : `Checked ${run.target_name} — no new prospects this time.`
}

/** Plain-language "what happened" sentence for a web crawler run — reused anywhere runs appear. */
export function summarizeCrawlRun(run: CrawlRun): string {
  if (run.status === 'running') return 'Web crawler run in progress…'
  if (run.status === 'failed') {
    return `Web crawler run didn't finish${run.error_text ? ` — ${run.error_text}` : ' — it will retry automatically.'}`
  }
  return run.prospects_created > 0
    ? `Web crawler found ${run.prospects_created} new organization${run.prospects_created === 1 ? '' : 's'}.`
    : 'Web crawler run finished — no new organizations this time.'
}

/** Plain-language "what happened" sentence for an AI search — reused anywhere runs appear. */
export function summarizeAiSearchJob(job: AISearchJob): string {
  if (AI_SEARCH_IN_PROGRESS.has(job.status)) return `Searching for "${job.seed_topic}"…`
  if (job.status === 'failed') return `AI search for "${job.seed_topic}" failed${job.error_text ? ` — ${job.error_text}` : '.'}`
  return job.prospects_created > 0
    ? `AI search for "${job.seed_topic}" found ${job.prospects_created} new prospect${job.prospects_created === 1 ? '' : 's'}.`
    : `AI search for "${job.seed_topic}" finished — no strong matches this time.`
}
