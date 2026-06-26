/** Classify grading / API errors for user-facing banners. */

const RATE_LIMIT_RE = /429|rate limit|quota|token.?limit|free-models-per|exhausted|too many requests|resource_exhausted|insufficient.*credit/i;

export function classifyGradingError(message) {
  const raw = String(message || '').trim();
  const lower = raw.toLowerCase();

  if (RATE_LIMIT_RE.test(raw)) {
    return {
      kind: 'rate_limit',
      title: 'AI quota or rate limit reached',
      message: raw || 'The grading service hit a provider rate or token limit.',
      hint: 'Wait for the daily limit to reset, add OpenRouter credits, or set GRADE_LLM_PROVIDER=gemini in .env and restart the API.',
    };
  }

  if (lower.includes('already running') || lower.includes('wait for it to finish')) {
    return {
      kind: 'busy',
      title: 'Grading already in progress',
      message: raw,
      hint: 'Wait for the current job to finish, then try Re-grade again.',
    };
  }

  if (lower.includes('network') || lower.includes('failed to fetch') || lower.includes('api unavailable')) {
    return {
      kind: 'network',
      title: 'Cannot reach grading server',
      message: raw,
      hint: 'Check that the API is running on port 8000 and refresh this page.',
    };
  }

  if (/^http 500$/i.test(raw) || lower.includes('internal server error') || lower.includes('importerror')) {
    return {
      kind: 'server',
      title: 'Grading server error',
      message: raw === 'HTTP 500'
        ? 'The grading API crashed or failed to start a job. Restart the API server and try again.'
        : raw,
      hint: 'If this persists, check the API terminal for Python tracebacks.',
    };
  }

  return {
    kind: 'error',
    title: 'Grading failed',
    message: raw || 'Something went wrong during grading.',
    hint: null,
  };
}

export function rateLimitFromResult(result) {
  if (!result?.questions?.length) return null;
  const hit = result.questions.find(
    (q) =>
      (q.flags || []).map(String).includes('llm_rate_limited') ||
      RATE_LIMIT_RE.test(String(q.feedback || '')),
  );
  if (!hit) return null;
  return classifyGradingError(hit.feedback || 'LLM rate or token limit reached during grading.');
}
