// GRADE API client — talks to FastAPI (proxied in dev via vite.config.js)

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

function buildUrl(endpoint) {
  return `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
}

async function parseResponse(res) {
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    const data = await res.json();
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      let jobId = null;
      if (typeof data?.detail === 'string') {
        detail = data.detail;
      } else if (Array.isArray(data?.detail)) {
        detail = data.detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
      } else if (typeof data?.detail === 'object' && data.detail !== null) {
        detail = data.detail.message || JSON.stringify(data.detail);
        if (data.detail.job_id) {
          jobId = data.detail.job_id;
        }
      }
      const err = new Error(detail);
      err.status = res.status;
      if (jobId) {
        err.jobId = jobId;
      }
      throw err;
    }
    return data;
  }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res;
}

/** JSON GET/POST; returns null on network failure (demo fallback). */
export async function apiFetch(endpoint, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  try {
    const res = await fetch(buildUrl(endpoint), { ...options, headers });
    return await parseResponse(res);
  } catch (err) {
    console.warn(`[GRADE] API unavailable (${endpoint}):`, err.message);
    return null;
  }
}

/** JSON request that surfaces errors to the caller (uploads, evaluate). */
export async function apiRequest(endpoint, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(buildUrl(endpoint), { ...options, headers });
  return parseResponse(res);
}

export async function checkApiHealth() {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const r = await fetch(buildUrl('/health'), { signal: AbortSignal.timeout(8000) });
      if (r.ok) return true;
    } catch {
      if (attempt === 0) await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  return false;
}

export async function getHealth() {
  return apiFetch('/health');
}

export async function getDatabaseStatus() {
  return apiFetch('/api/database/status');
}

export async function getIntegrations() {
  return apiFetch('/api/integrations');
}

export async function getExams() {
  return apiFetch('/api/exams');
}

export async function getExamDetail(examId) {
  return apiFetch(`/api/exams/${encodeURIComponent(examId)}`);
}

export async function getExamQuestionPrompts(examId) {
  return apiFetch(`/api/exams/${encodeURIComponent(examId)}/question-prompts`);
}

export async function getExamStats(examId) {
  return apiFetch(`/api/exams/${encodeURIComponent(examId)}/stats`);
}

export async function getExamQuestionCount(examId) {
  return apiFetch(`/api/exams/${encodeURIComponent(examId)}/question-count`);
}

export async function getExamKeyChunks(examId) {
  return apiFetch(`/api/exam/${encodeURIComponent(examId)}/key-chunks`);
}

export async function getSheetChunks(sheetId) {
  return apiFetch(`/api/sheet/${encodeURIComponent(sheetId)}/chunks`);
}

export async function getSheetPreview(sheetId, { rebuild = false } = {}) {
  const q = rebuild ? '?rebuild=true' : '';
  return apiFetch(`/api/sheet/${encodeURIComponent(sheetId)}/preview${q}`);
}

export async function getSheetQuestionRegions(sheetId) {
  return apiFetch(`/api/sheet/${encodeURIComponent(sheetId)}/question-regions`);
}

export function sheetPreviewImageUrl(sheetId, page = 1) {
  const p = Math.max(1, Number(page) || 1);
  return buildUrl(`/api/sheet/${encodeURIComponent(sheetId)}/preview/page/${p}.png`);
}

export async function checkSheetPreviewImage(sheetId, page = 1) {
  try {
    const res = await fetch(sheetPreviewImageUrl(sheetId, page), { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}

export async function searchRag(query, { examId, sheetId, topK = 5 } = {}) {
  return apiRequest('/api/rag/search', {
    method: 'POST',
    body: JSON.stringify({
      query,
      exam_id: examId || null,
      sheet_id: sheetId || null,
      top_k: topK,
    }),
  });
}

export async function patchQuestionScore(resultId, regionIndex, { awardedMarks, feedback }) {
  return apiRequest(`/result/${encodeURIComponent(resultId)}/questions/${regionIndex}`, {
    method: 'PATCH',
    body: JSON.stringify({
      awarded_marks: awardedMarks,
      feedback: feedback ?? undefined,
    }),
  });
}

export async function getJob(jobId) {
  return apiRequest(`/jobs/${encodeURIComponent(jobId)}`);
}

export async function createUploadBundleJob(examId, keyFile, sheetFile, { defaultMaxMarks = 4, regionsPerPage } = {}) {
  const form = new FormData();
  form.append('exam_id', examId.trim());
  form.append('key_file', keyFile, keyFile.name || 'key.docx');
  form.append('sheet_file', sheetFile, sheetFile.name || 'sheet.pdf');
  form.append('default_max_marks', String(defaultMaxMarks));
  if (regionsPerPage) {
    const spec = Array.isArray(regionsPerPage) ? regionsPerPage.join(',') : String(regionsPerPage);
    if (spec.trim()) form.append('regions_per_page', spec);
  }
  return apiRequest('/jobs/upload-exam-bundle', { method: 'POST', body: form });
}

export async function createUploadSheetJob(examId, file, { regionsPerPage } = {}) {
  const form = new FormData();
  form.append('exam_id', examId);
  form.append('file', file);
  if (regionsPerPage) {
    const spec = Array.isArray(regionsPerPage) ? regionsPerPage.join(',') : String(regionsPerPage);
    if (spec.trim()) form.append('regions_per_page', spec);
  }
  return apiRequest('/jobs/upload-sheet', { method: 'POST', body: form });
}

export async function createEvaluateJob(sheetId, examId, options = {}) {
  return apiRequest('/jobs/evaluate', {
    method: 'POST',
    body: JSON.stringify({
      sheet_id: sheetId,
      exam_id: examId,
      top_k: options.topK ?? 3,
      expected_num_regions: options.expectedNumRegions ?? null,
      regions_per_page: options.regionsPerPage ?? null,
      use_consensus_ocr: options.useConsensusOcr ?? false,
      force_regrade: options.forceRegrade ?? false,
    }),
  });
}


export async function getSheets(examId) {
  const q = examId ? `?exam_id=${encodeURIComponent(examId)}` : '';
  return apiFetch(`/api/sheets${q}`);
}

export async function getResults({ examId, sheetId, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (examId) params.set('exam_id', examId);
  if (sheetId) params.set('sheet_id', sheetId);
  params.set('limit', String(limit));
  const q = params.toString();
  return apiFetch(`/api/results${q ? `?${q}` : ''}`);
}

/** Latest stored grade for a sheet, if evaluate already finished. */
export async function findExistingResult(sheetId, examId) {
  if (!sheetId) return null;
  const rows = await getResults({ sheetId, examId: examId || undefined, limit: 1 });
  if (!rows?.length) return null;
  const resultId = rows[0].id || rows[0].result_id;
  if (!resultId) return null;
  return getResult(resultId);
}

export async function getResult(resultId) {
  return apiFetch(`/result/${encodeURIComponent(resultId)}`);
}

export async function getMetricsOverview() {
  return apiFetch('/api/metrics/overview');
}

export async function evaluateSheet(sheetId, examId, options = {}) {
  return apiRequest('/evaluate', {
    method: 'POST',
    body: JSON.stringify({
      sheet_id: sheetId,
      exam_id: examId,
      top_k: options.topK ?? 3,
      expected_num_regions: options.expectedNumRegions ?? null,
      regions_per_page: options.regionsPerPage ?? null,
      use_consensus_ocr: options.useConsensusOcr ?? false,
      force_regrade: options.forceRegrade ?? false,
    }),
  });
}

export async function uploadExamBundle(examId, keyFile, sheetFile, { defaultMaxMarks = 4, regionsPerPage } = {}) {
  const form = new FormData();
  form.append('exam_id', examId.trim());
  form.append('key_file', keyFile, keyFile.name || 'key.docx');
  form.append('sheet_file', sheetFile, sheetFile.name || 'sheet.pdf');
  form.append('default_max_marks', String(defaultMaxMarks));
  if (regionsPerPage) {
    const spec = Array.isArray(regionsPerPage) ? regionsPerPage.join(',') : String(regionsPerPage);
    if (spec.trim()) form.append('regions_per_page', spec);
  }
  return apiRequest('/upload/exam-bundle', { method: 'POST', body: form });
}

export async function uploadSheet(examId, file, { regionsPerPage } = {}) {
  const form = new FormData();
  form.append('exam_id', examId);
  form.append('file', file);
  if (regionsPerPage) {
    const spec = Array.isArray(regionsPerPage) ? regionsPerPage.join(',') : String(regionsPerPage);
    if (spec.trim()) form.append('regions_per_page', spec);
  }
  return apiRequest('/upload/sheet', { method: 'POST', body: form });
}

export async function uploadKeyFile(examId, file, defaultMaxMarks = 4) {
  const form = new FormData();
  if (examId) form.append('exam_id', examId);
  form.append('file', file);
  form.append('default_max_marks', String(defaultMaxMarks));
  return apiRequest('/upload/key/file', { method: 'POST', body: form });
}

export function sheetFileUrl(sheetId) {
  return buildUrl(`/sheet/${encodeURIComponent(sheetId)}/file`);
}

export function reportPdfUrl(resultId) {
  return buildUrl(`/report/${encodeURIComponent(resultId)}/pdf`);
}

export const GRADE_SESSION = {
  examId: 'grade:lastExamId',
  sheetId: 'grade:lastSheetId',
  resultId: 'grade:lastResultId',
  filename: 'grade:lastFilename',
  expectedNumRegions: 'grade:expectedNumRegions',
  regionsPerPage: 'grade:regionsPerPage',
  questionPrompts: 'grade:questionPrompts',
  jobId: 'grade:lastJobId',
};

export function parseRegionsPerPage(spec) {
  if (!spec || !String(spec).trim()) return null;
  const parts = String(spec).split(',').map((s) => parseInt(s.trim(), 10));
  if (parts.some((n) => Number.isNaN(n) || n < 1)) return null;
  return parts;
}

export function parseRegionsSum(spec) {
  const parts = parseRegionsPerPage(spec);
  if (!parts) return null;
  return parts.reduce((a, b) => a + b, 0);
}

export function saveGradeSession({ examId, sheetId, resultId, filename, expectedNumRegions, regionsPerPage, jobId }) {
  if (examId) sessionStorage.setItem(GRADE_SESSION.examId, examId);
  if (sheetId) sessionStorage.setItem(GRADE_SESSION.sheetId, sheetId);
  if (resultId) sessionStorage.setItem(GRADE_SESSION.resultId, resultId);
  if (filename) sessionStorage.setItem(GRADE_SESSION.filename, filename);
  if (jobId) sessionStorage.setItem(GRADE_SESSION.jobId, jobId);
  if (expectedNumRegions != null && expectedNumRegions !== '') {
    sessionStorage.setItem(GRADE_SESSION.expectedNumRegions, String(expectedNumRegions));
  }
  if (regionsPerPage != null) {
    const spec = Array.isArray(regionsPerPage) ? regionsPerPage.join(',') : String(regionsPerPage);
    if (spec.trim()) sessionStorage.setItem(GRADE_SESSION.regionsPerPage, spec);
  }
}

export function loadGradeSession() {
  const raw = sessionStorage.getItem(GRADE_SESSION.expectedNumRegions);
  const expectedNumRegions = raw ? parseInt(raw, 10) : null;
  const regionsPerPage = parseRegionsPerPage(sessionStorage.getItem(GRADE_SESSION.regionsPerPage) || '');
  let questionPrompts = {};
  try {
    const stored = sessionStorage.getItem(GRADE_SESSION.questionPrompts);
    if (stored) questionPrompts = JSON.parse(stored);
  } catch {
    questionPrompts = {};
  }
  return {
    examId: sessionStorage.getItem(GRADE_SESSION.examId) || '',
    sheetId: sessionStorage.getItem(GRADE_SESSION.sheetId) || '',
    resultId: sessionStorage.getItem(GRADE_SESSION.resultId) || '',
    filename: sessionStorage.getItem(GRADE_SESSION.filename) || '',
    jobId: sessionStorage.getItem(GRADE_SESSION.jobId) || '',
    expectedNumRegions: Number.isNaN(expectedNumRegions) ? null : expectedNumRegions,
    regionsPerPage,
    questionPrompts,
  };
}
