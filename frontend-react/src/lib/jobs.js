import { getJob } from './api';

export const JOB_STAGE_LABELS = {
  uploading: 'Saving file…',
  parsing_key: 'Reading marking scheme…',
  ingest_keys: 'Indexing model answers…',
  ingest_sheet: 'Scanning handwriting…',
  ocr_evaluate: 'Grading questions…',
  done: 'Complete',
  error: 'Something went wrong',
};

export function stageLabel(stage) {
  return JOB_STAGE_LABELS[stage] || stage || 'Working…';
}

export async function pollJob(jobId, { intervalMs = 2000, onUpdate } = {}) {
  if (!jobId) throw new Error('job_id required');
  for (;;) {
    const job = await getJob(jobId);
    if (!job) throw new Error('Job not found');
    onUpdate?.(job);
    if (job.status === 'completed' || job.status === 'failed') return job;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
