import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { formatExamName } from '../lib/examLabels';
import { hintForExam, pageForRegionIndex } from '../lib/examLayouts';
import { confColor } from '../lib/confidence';
import { pollJob, stageLabel } from '../lib/jobs';
import {
  findExistingResult,
  getExamQuestionPrompts,
  getExamStats,
  getResult,
  getSheetPreview,
  getSheetQuestionRegions,
  loadGradeSession,
  parseRegionsPerPage,
  saveGradeSession,
  sheetFileUrl,
  sheetPreviewImageUrl,
  checkSheetPreviewImage,
  createEvaluateJob,
  patchQuestionScore,
  GRADE_SESSION,
} from '../lib/api';

function loadHitlEnabled() {
  try {
    const cfg = JSON.parse(localStorage.getItem('grade-config') || '{}');
    return Boolean(cfg.human_in_loop);
  } catch {
    return false;
  }
}

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function isPdfFilename(name) {
  return /\.pdf$/i.test(name || '');
}

const PREVIEW_SEGMENT_SCALE = 3.0;

function scaleBboxToPreview(bbox, fromScale = PREVIEW_SEGMENT_SCALE, toScale = 2.0) {
  if (!bbox?.length) return bbox;
  const f = toScale / fromScale;
  return bbox.map((v) => Math.round(v * f));
}

function formatPageLabel(pageStart, pageEnd) {
  const ps = Number(pageStart) || 1;
  const pe = Number(pageEnd) || ps;
  if (pe > ps) return `Pages ${ps}–${pe}`;
  return `Page ${ps}`;
}

function SheetPreview({
  sheetId,
  pdfUrl,
  filename,
  activeRegionIndex = 0,
  activeQuestionId = '',
  regionsPerPage = null,
  questionRegions = [],
  previewPage = 1,
  onPreviewPageChange = null,
  refreshKey = 0,
}) {
  const isPdf = isPdfFilename(filename);
  const canvasRef = useRef(null);
  const [regions, setRegions] = useState([]);
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });
  const [pageCount, setPageCount] = useState(1);
  const [previewReady, setPreviewReady] = useState(false);
  const [mode, setMode] = useState('pdf');
  const [pdfBlobUrl, setPdfBlobUrl] = useState('');
  const [pdfLoading, setPdfLoading] = useState(false);
  const [loadError, setLoadError] = useState('');

  const [layout, setLayout] = useState(regionsPerPage);

  useEffect(() => {
    setLayout(regionsPerPage);
  }, [regionsPerPage]);

  useEffect(() => {
    if (!sheetId) {
      setRegions([]);
      setPreviewReady(false);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      try {
        const meta = await getSheetPreview(sheetId, { rebuild: refreshKey > 0 });
        if (cancelled) return;
        const pages = Number(meta?.page_count) || 0;
        const hasImage = pages > 0 && await checkSheetPreviewImage(sheetId, 1);
        setPreviewReady(hasImage);
        if (hasImage) {
          setMode('image');
          if (meta?.regions) setRegions(meta.regions);
          if (pages) setPageCount(pages);
          if (meta?.regions_per_page?.length) setLayout(meta.regions_per_page);
        } else if (isPdf) {
          setMode('pdf');
        }
      } catch {
        if (!cancelled && isPdf) setMode('pdf');
      }
    })();
    return () => { cancelled = true; };
  }, [sheetId, isPdf, refreshKey]);

  useEffect(() => {
    const activeMeta = questionRegions.find(
      (q) => (activeQuestionId && String(q.question_id) === String(activeQuestionId))
        || (q.region_index ?? q.question_index) === activeRegionIndex,
    );
    const target = Number(activeMeta?.page_start) || pageForRegionIndex(activeRegionIndex, layout);
    if (target && onPreviewPageChange) {
      onPreviewPageChange(target);
      return;
    }
    if (!onPreviewPageChange) return;
    const matches = regions.filter((r) => r.region_index === activeRegionIndex);
    const page = matches.length
      ? Math.min(...matches.map((r) => r.page ?? 1))
      : pageForRegionIndex(activeRegionIndex, layout);
    if (page) onPreviewPageChange(page);
  }, [activeRegionIndex, questionRegions, regions, layout, onPreviewPageChange]);

  const displayPage = previewPage || 1;

  useEffect(() => {
    setImgSize({ w: 0, h: 0 });
  }, [displayPage, sheetId]);

  useEffect(() => {
    if (!imgSize.w) return undefined;
    const timer = setTimeout(() => {
      const el = canvasRef.current?.querySelector('.sheet-region-box.active');
      el?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    }, 80);
    return () => clearTimeout(timer);
  }, [activeRegionIndex, displayPage, imgSize.w]);

  useEffect(() => {
    if (!pdfUrl || !isPdf) {
      setPdfBlobUrl('');
      return undefined;
    }
    let revoked = '';
    let cancelled = false;
    setPdfLoading(true);
    (async () => {
      try {
        const res = await fetch(pdfUrl);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (cancelled) return;
        revoked = URL.createObjectURL(blob);
        setPdfBlobUrl(revoked);
        setLoadError('');
      } catch (err) {
        if (!cancelled) {
          setPdfBlobUrl('');
          setLoadError(err.message || 'Could not load PDF');
        }
      } finally {
        if (!cancelled) setPdfLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [pdfUrl, isPdf]);

  const handleImageError = () => {
    setPreviewReady(false);
    setLoadError('');
    if (isPdf) setMode('pdf');
  };

  if (!sheetId && !pdfUrl) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--outline)' }}>
        No preview yet — submit a paper from Grade new papers
      </div>
    );
  }

  const imageUrl = sheetId
    ? `${sheetPreviewImageUrl(sheetId, displayPage)}${refreshKey ? `?v=${refreshKey}` : ''}`
    : '';
  const visibleRegions = regions.filter((r) => (r.page ?? 1) === displayPage);
  const activeMeta = questionRegions.find(
    (q) => (activeQuestionId && String(q.question_id) === String(activeQuestionId))
      || (q.region_index ?? q.question_index) === activeRegionIndex,
  );
  const activeSegments = (activeMeta?.segments || []).filter((s) => (s.page ?? 1) === displayPage);
  const overlayItems = visibleRegions.length
    ? visibleRegions.map((r, ri) => ({
      key: `raw-${r.raw_region_index ?? ri}-${r.page}`,
      bbox: r.bbox,
      regionIndex: r.region_index ?? ri,
      label: `Q${(r.region_index ?? ri) + 1}`,
    }))
    : activeSegments.map((seg, si) => ({
      key: `seg-${seg.raw_region_index ?? si}-${seg.page}`,
      bbox: scaleBboxToPreview(seg.bbox),
      regionIndex: activeRegionIndex,
      label: activeQuestionId || `Q${activeRegionIndex + 1}`,
    }));
  const effectivePageCount = pageCount > 1
    ? pageCount
    : (regions.length
      ? Math.max(...regions.map((r) => r.page ?? 1))
      : (layout?.length || 1));
  const showImageMode = mode === 'image' && previewReady && sheetId;
  const showPdfMode = mode === 'pdf' && isPdf;
  const showRasterFallback = mode === 'image' && !previewReady && !isPdf && pdfUrl;

  return (
    <div className="sheet-preview-pdf">
      <div className="sheet-preview-toolbar">
        {previewReady && sheetId && (
          <button type="button" className={`btn btn-sm ${showImageMode ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => { setMode('image'); setLoadError(''); }}>Page + regions</button>
        )}
        {isPdf && pdfUrl && (
          <button type="button" className={`btn btn-sm ${showPdfMode ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => { setMode('pdf'); setLoadError(''); }}>Full PDF</button>
        )}
        {showImageMode && effectivePageCount > 1 && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={displayPage <= 1}
              onClick={() => onPreviewPageChange?.(displayPage - 1)}
              title="Previous page"
            >
              ← Page
            </button>
            <span style={{ fontSize: '0.75rem', color: 'var(--outline)', minWidth: '5rem', textAlign: 'center' }}>
              {displayPage} / {effectivePageCount}
            </span>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={displayPage >= effectivePageCount}
              onClick={() => onPreviewPageChange?.(displayPage + 1)}
              title="Next page"
            >
              Page →
            </button>
            {activeMeta && Number(activeMeta.page_end) > Number(activeMeta.page_start) && (
              <>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={displayPage <= Number(activeMeta.page_start)}
                  onClick={() => onPreviewPageChange?.(Math.max(Number(activeMeta.page_start), displayPage - 1))}
                >
                  ← Part
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={displayPage >= Number(activeMeta.page_end)}
                  onClick={() => onPreviewPageChange?.(Math.min(Number(activeMeta.page_end), displayPage + 1))}
                >
                  Part →
                </button>
              </>
            )}
            <span style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>
              {activeMeta
                ? `${formatPageLabel(activeMeta.page_start, activeMeta.page_end)} · viewing ${displayPage}/${effectivePageCount}`
                : `Page ${displayPage} / ${effectivePageCount}`}
            </span>
          </div>
        )}
      </div>

      {showImageMode ? (
        <div className="sheet-preview-canvas" ref={canvasRef}>
          <div className="sheet-preview-stage">
            <img
              key={`${sheetId}-p${displayPage}`}
              src={imageUrl}
              alt={`Answer sheet page ${displayPage}`}
              className="sheet-preview-image"
              onLoad={(e) => setImgSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
              onError={handleImageError}
            />
            {imgSize.w > 0 && overlayItems.length > 0 && (
              <div className="sheet-preview-overlays">
                {overlayItems.map((item) => {
                  const [x, y, w, h] = item.bbox || [];
                  if (w == null) return null;
                  const isActive = item.regionIndex === activeRegionIndex;
                  return (
                    <div
                      key={item.key}
                      className={`sheet-region-box${isActive ? ' active' : ''}`}
                      style={{
                        left: `${(x / imgSize.w) * 100}%`,
                        top: `${(y / imgSize.h) * 100}%`,
                        width: `${(w / imgSize.w) * 100}%`,
                        height: `${(h / imgSize.h) * 100}%`,
                      }}
                      title={item.label}
                    >
                      <span className="sheet-region-label">{item.label}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : showRasterFallback ? (
        <img src={pdfUrl} alt="Uploaded answer sheet" className="sheet-preview-image" />
      ) : showPdfMode ? (
        <div className="sheet-preview-pdf-embed">
          {pdfLoading && !pdfBlobUrl && !loadError && (
            <p style={{ padding: '1rem', color: 'var(--outline)', fontSize: '0.875rem' }}>Loading PDF…</p>
          )}
          {loadError ? (
            <p className="sheet-preview-error">
              {loadError}.{' '}
              {pdfUrl && <a href={pdfUrl} target="_blank" rel="noreferrer">Open PDF in new tab</a>}
            </p>
          ) : (
            <embed
              src={pdfBlobUrl || pdfUrl}
              type="application/pdf"
              className="sheet-preview-embed"
              title="Uploaded answer sheet"
            />
          )}
        </div>
      ) : (
        <p style={{ padding: '1rem', color: 'var(--outline)', fontSize: '0.875rem' }}>
          Preview unavailable.{' '}
          {pdfUrl && <a href={pdfUrl} target="_blank" rel="noreferrer">Open answer sheet</a>}
        </p>
      )}
    </div>
  );
}

function formatTextLabel(text) {
  const n = String(text || '').trim().length;
  return n > 0 ? ` (${n.toLocaleString()} chars)` : '';
}

function cleanedDiffersFromOcr(recognized, formatted) {
  const raw = String(recognized || '').trim();
  const clean = String(formatted || '').trim();
  if (!clean || !raw) return false;
  if (clean === raw) return false;
  const norm = (s) => s.replace(/\s+/g, ' ').toLowerCase();
  return norm(clean) !== norm(raw);
}

function truncate(text, max = 72) {
  const t = String(text || '').trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

function attachPrompts(questions, promptsById) {
  if (!questions?.length || !promptsById) return questions;
  return questions.map((q) => ({
    ...q,
    prompt: promptsById[q.questionId] || q.prompt || '',
  }));
}

function pickBetterQuestion(prev, q) {
  if (!prev) return q;
  const prevLen = Math.max(
    String(prev.recognized || '').trim().length,
    String(prev.formatted || '').trim().length,
  );
  const qLen = Math.max(
    String(q.recognized || '').trim().length,
    String(q.formatted || '').trim().length,
  );
  if (qLen > prevLen) return q;
  if (qLen < prevLen) return prev;
  if (q.score > prev.score) return q;
  if (q.score < prev.score) return prev;
  const prevRi = prev.regionIndex ?? 999;
  const qRi = q.regionIndex ?? 999;
  return qRi < prevRi ? q : prev;
}

function collapseByQuestionId(questions) {
  if (questions.length <= 6) return questions;
  const groups = new Map();
  for (const q of questions) {
    const qid = q.questionId || q.id.split('-r')[0];
    groups.set(qid, pickBetterQuestion(groups.get(qid), q));
  }
  const collapsed = Array.from(groups.values())
    .map((q) => ({ ...q, id: q.questionId || q.id, questionId: q.questionId || q.id, active: false }))
    .sort((a, b) => (a.regionIndex ?? 0) - (b.regionIndex ?? 0));
  if (collapsed.length >= questions.length) return questions;
  const firstWithText = collapsed.findIndex((q) => q.recognized?.trim());
  collapsed.forEach((q, i) => { q.active = i === (firstWithText >= 0 ? firstWithText : 0); });
  return collapsed;
}

function sessionWithLayout(session) {
  const layout = parseRegionsPerPage(hintForExam(session.examId));
  if (layout?.length) {
    return { ...session, regionsPerPage: layout };
  }
  if (session.regionsPerPage?.length) return session;
  return session;
}

function expectedLayoutFlag(session) {
  const layout = parseRegionsPerPage(hintForExam(session.examId)) || session.regionsPerPage;
  if (!layout?.length) return null;
  return `layout:${layout.join(',')}`;
}

function layoutNeedsRegrade(session) {
  const expected = parseRegionsPerPage(hintForExam(session.examId));
  const current = session.regionsPerPage;
  if (!expected?.length || !session.examId) return false;
  if (!current?.length) return true;
  return current.join(',') !== expected.join(',');
}

function resultNeedsRegrade(result, keyCount, session = null) {
  if (!result?.questions?.length || !keyCount) return false;
  if (session && layoutNeedsRegrade(session)) return true;
  if (result.questions.length !== keyCount) return true;
  const flags = new Set((result.flags || []).map(String));
  if (!flags.has('segmentation_v3')) return true;
  const layoutFlag = session ? expectedLayoutFlag(sessionWithLayout(session)) : null;
  if (layoutFlag && !flags.has(layoutFlag)) return true;
  // Invalidate grades run with single-strip layout on multi-question CIE sheets.
  if (flags.has('layout:1') && session?.examId && hintForExam(session.examId) === '3,1,2,1') {
    return true;
  }
  if (flags.has('layout:3,1,2,1') && session?.examId && hintForExam(session.examId) === '3,1,1,2') {
    return true;
  }
  return false;
}

async function pickEvaluationResult(session, keyCount) {
  const candidates = [];
  const seen = new Set();
  const push = (result) => {
    const id = result?.result_id || result?.id;
    if (!result || !id || seen.has(id)) return;
    seen.add(id);
    candidates.push(result);
  };

  if (session.resultId) {
    const stored = await getResult(session.resultId);
    push(stored);
  }
  const latest = await findExistingResult(session.sheetId, session.examId);
  push(latest);

  if (!candidates.length) return null;

  const fresh = candidates.filter((r) => !resultNeedsRegrade(r, keyCount, session));
  const pool = fresh.length ? fresh : candidates;
  pool.sort((a, b) => {
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
    return tb - ta;
  });
  return pool[0];
}

function normalizeResultQuestions(rawQuestions, keyCount) {
  if (!keyCount || rawQuestions.length <= keyCount) return rawQuestions;
  const slots = [];
  for (let ri = 0; ri < keyCount; ri++) {
    const candidates = rawQuestions.filter((q) => (q.region_index ?? -1) === ri);
    if (!candidates.length) continue;
    const best = candidates.reduce((a, b) => {
      const aLen = String(a.student_answer || a.ocr_raw || '').trim().length;
      const bLen = String(b.student_answer || b.ocr_raw || '').trim().length;
      return bLen > aLen ? b : a;
    });
    slots.push(best);
  }
  return slots.length === keyCount ? slots : rawQuestions;
}

function mapQuestions(result, promptsById = {}, keyCount = 0) {
  if (!result?.questions?.length) return [];
  const normalized = normalizeResultQuestions(result.questions, keyCount || result.questions.length);
  const mapped = normalized.map((q, i) => {
    const region = q.region_index ?? i;
    const qid = q.question_id || `Q${i + 1}`;
    return {
      id: `${qid}-r${region}`,
      questionId: qid,
      regionIndex: region,
      pageStart: q.page_start ?? 1,
      pageEnd: q.page_end ?? q.page_start ?? 1,
      pages: q.pages || [],
      pageLabel: formatPageLabel(q.page_start, q.page_end),
      prompt: promptsById[qid] || q.question_text || '',
      confidence: Math.round((q.ocr_confidence ?? 0.85) * 100),
      score: q.awarded_marks ?? 0,
      maxScore: q.max_marks ?? 0,
      active: i === 0,
      recognized: q.ocr_raw || q.student_answer || '',
      formatted: q.student_answer || '',
      feedback: q.feedback || '',
      points: q.rubric_scores
        ? [
            { ok: (q.rubric_scores.factual_accuracy ?? 0) >= 2, text: `Accuracy — ${q.rubric_scores.factual_accuracy}/4` },
            { ok: (q.rubric_scores.conceptual_completeness ?? 0) >= 2, text: `Completeness — ${q.rubric_scores.conceptual_completeness}/4` },
            { ok: (q.rubric_scores.reasoning ?? 0) >= 2, text: `Reasoning — ${q.rubric_scores.reasoning}/4` },
            { ok: (q.rubric_scores.domain_terminology ?? 0) >= 2, text: `Terminology — ${q.rubric_scores.domain_terminology}/4` },
          ]
        : [],
    };
  });
  return collapseByQuestionId(mapped);
}

const EMPTY_STATE = [
  {
    id: '—',
    questionId: '—',
    prompt: '',
    confidence: 0,
    score: 0,
    maxScore: 0,
    active: true,
    recognized: 'Grade a paper from Submit papers, then return here to see question-by-question scores.',
    points: [],
  },
];

export default function EvaluatorPage() {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState(EMPTY_STATE);
  const [zoom, setZoom] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingSeconds, setLoadingSeconds] = useState(0);
  const [error, setError] = useState('');
  const [meta, setMeta] = useState({
    filename: '',
    examId: '',
    sheetId: '',
    resultId: '',
    resultCreatedAt: '',
    regionsPerPage: null,
  });
  const [questionPrompts, setQuestionPrompts] = useState({});
  const [sheetPreviewUrl, setSheetPreviewUrl] = useState('');
  const [previewPage, setPreviewPage] = useState(1);
  const [previewRefresh, setPreviewRefresh] = useState(0);
  const [questionRegions, setQuestionRegions] = useState([]);
  const [staleResult, setStaleResult] = useState(false);
  const [hitlEnabled] = useState(loadHitlEnabled);
  const [overrideDraft, setOverrideDraft] = useState({});
  const [savingOverride, setSavingOverride] = useState(false);
  const [evalProgress, setEvalProgress] = useState(0);
  const [evalStage, setEvalStage] = useState('');
  const pageRef = useRef(null);
  const runRef = useRef(0);
  const sessionRef = useRef(loadGradeSession());
  const applyResultRef = useRef(null);

  const runEvaluate = async (session, { forceRegrade = false } = {}) => {
    const withLayout = sessionWithLayout(session);
    if (withLayout.regionsPerPage && !session.regionsPerPage) {
      saveGradeSession({ regionsPerPage: withLayout.regionsPerPage });
    }
    let jobId = null;
    try {
      const job = await createEvaluateJob(withLayout.sheetId, withLayout.examId, {
        expectedNumRegions: withLayout.expectedNumRegions ?? undefined,
        regionsPerPage: withLayout.regionsPerPage ?? undefined,
        forceRegrade,
      });
      jobId = job.job_id;
    } catch (err) {
      if (err.status === 409 && err.jobId) {
        jobId = err.jobId;
      } else {
        throw err;
      }
    }
    sessionStorage.setItem(GRADE_SESSION.jobId, jobId);
    const finalJob = await pollJob(jobId, {
      onUpdate: (j) => {
        setEvalProgress(j.progress || 0);
        setEvalStage(stageLabel(j.stage));
      },
    });
    sessionStorage.removeItem(GRADE_SESSION.jobId);
    if (finalJob.status === 'failed') throw new Error(finalJob.error || 'Evaluation failed');
    return finalJob.result;
  };

  const checkStale = async (result, examId) => {
    if (!result || !examId) return false;
    const stats = await getExamStats(examId);
    if (!stats) return false;
    const keysAt = stats.keys_latest_at ? new Date(stats.keys_latest_at).getTime() : 0;
    const resultAt = result.created_at ? new Date(result.created_at).getTime() : 0;
    if (keysAt && resultAt && keysAt > resultAt) return true;
    if (stats.key_count && result.questions?.length && stats.key_count !== result.questions.length) return true;
    return false;
  };

  const applyResult = useCallback((result, session, keyCount = 0) => {
    const mapped = mapQuestions(result, { ...session.questionPrompts, ...questionPrompts }, keyCount);
    if (mapped.length) {
      const firstWithText = mapped.findIndex((q) => q.recognized?.trim());
      const activeIdx = firstWithText >= 0 ? firstWithText : 0;
      mapped.forEach((q, i) => { q.active = i === activeIdx; });
    }
    setQuestions(mapped.length ? mapped : EMPTY_STATE);
    setMeta({
      filename: session.filename,
      examId: result.exam_id || session.examId,
      sheetId: result.sheet_id || session.sheetId,
      resultId: result.result_id,
      resultCreatedAt: result.created_at || '',
      regionsPerPage: sessionWithLayout(session).regionsPerPage ?? null,
    });
    const sid = result.sheet_id || session.sheetId;
    if (sid) setSheetPreviewUrl(sheetFileUrl(sid));
    setPreviewRefresh((n) => n + 1);
    checkStale(result, result.exam_id || session.examId).then(setStaleResult);
  }, [questionPrompts]);

  applyResultRef.current = applyResult;

  useEffect(() => {
    if (!loading) {
      setLoadingSeconds(0);
      return undefined;
    }
    const started = Date.now();
    const timer = setInterval(() => {
      setLoadingSeconds(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    if (!questionRegions.length) return undefined;
    setQuestions((prev) => prev.map((q) => {
      const meta = questionRegions.find(
        (item) => (item.region_index ?? item.question_index) === (q.regionIndex ?? 0)
          || String(item.question_id) === String(q.questionId),
      );
      if (!meta) return q;
      const pageStart = meta.page_start ?? 1;
      const pageEnd = meta.page_end ?? pageStart;
      return {
        ...q,
        pageStart,
        pageEnd,
        pages: meta.pages || [],
        pageLabel: formatPageLabel(pageStart, pageEnd),
      };
    }));
  }, [questionRegions]);

  useEffect(() => {
    if (!meta.sheetId) {
      setQuestionRegions([]);
      setPreviewPage(1);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      const data = await getSheetQuestionRegions(meta.sheetId);
      if (cancelled || !data?.question_regions) return;
      setQuestionRegions(data.question_regions);
    })();
    return () => { cancelled = true; };
  }, [meta.sheetId]);

  useEffect(() => {
    if (!meta.examId) return undefined;
    let cancelled = false;
    (async () => {
      const rows = await getExamQuestionPrompts(meta.examId);
      if (cancelled || !rows?.length) return;
      const map = Object.fromEntries(rows.map((r) => [r.question_id, r.prompt]));
      setQuestionPrompts(map);
      setQuestions((prev) => attachPrompts(prev, map));
    })();
    return () => { cancelled = true; };
  }, [meta.examId]);

  useEffect(() => {
    const runId = ++runRef.current;
    let cancelled = false;

    (async () => {
      const session = sessionWithLayout(loadGradeSession());
      if (!session.sheetId || !session.examId) {
        if (session.resultId) {
          setLoading(true);
          const cached = await getResult(session.resultId);
          if (!cancelled && runId === runRef.current && cached) {
            const prompts = cached.exam_id
              ? await getExamQuestionPrompts(cached.exam_id)
              : [];
            const keyCount = prompts?.length ?? 0;
            const best = await pickEvaluationResult(
              { ...session, sheetId: cached.sheet_id, examId: cached.exam_id, resultId: cached.result_id },
              keyCount,
            );
            if (keyCount && best && resultNeedsRegrade(best, keyCount, session) && cached.sheet_id && cached.exam_id) {
              const reg = await runEvaluate(
                { ...session, sheetId: cached.sheet_id, examId: cached.exam_id },
                { forceRegrade: true },
              );
              if (!cancelled && runId === runRef.current && reg) {
                saveGradeSession({ resultId: reg.result_id, sheetId: reg.sheet_id, examId: reg.exam_id });
                if (applyResultRef.current) applyResultRef.current(reg, { ...session, sheetId: reg.sheet_id, examId: reg.exam_id }, keyCount);
              }
            } else if (best) {
              if (applyResultRef.current) applyResultRef.current(best, session, keyCount);
            } else {
              if (applyResultRef.current) applyResultRef.current(cached, session, keyCount);
            }
          }
          if (!cancelled && runId === runRef.current) setLoading(false);
        }
        return;
      }

      setMeta({
        filename: session.filename,
        examId: session.examId,
        sheetId: session.sheetId,
        resultId: session.resultId,
        regionsPerPage: session.regionsPerPage ?? null,
      });
      setSheetPreviewUrl(sheetFileUrl(session.sheetId));
      setLoading(true);
      setError('');

      try {
        let result = null;
        const prompts = await getExamQuestionPrompts(session.examId);
        const keyCount = prompts?.length ?? 0;

        result = await pickEvaluationResult(session, keyCount);
        if (result && resultNeedsRegrade(result, keyCount, session)) {
          setStaleResult(true);
          saveGradeSession({ regionsPerPage: session.regionsPerPage });
          result = await runEvaluate(session, { forceRegrade: true });
        } else if (!result) {
          result = await runEvaluate(session);
        }
        if (!cancelled && runId === runRef.current && result) {
          saveGradeSession({ resultId: result.result_id });
          if (applyResultRef.current) applyResultRef.current(result, session, keyCount);
        }
      } catch (err) {
        if (!cancelled && runId === runRef.current) {
          setError(err.message || 'Evaluation failed');
        }
      } finally {
        if (!cancelled && runId === runRef.current) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, []);

  const totalScore = questions.reduce((a, q) => a + q.score, 0);
  const totalMax = questions.reduce((a, q) => a + q.maxScore, 0);

  const handleRegrade = async () => {
    const session = sessionWithLayout(loadGradeSession());
    if (!session.sheetId || !session.examId) return;
    setLoading(true);
    setError('');
    setEvalProgress(0);
    try {
      const prompts = await getExamQuestionPrompts(session.examId);
      const keyCount = prompts?.length ?? 0;
      const result = await runEvaluate(session, { forceRegrade: true });
      saveGradeSession({ resultId: result.result_id });
      applyResult(result, session, keyCount);
      setStaleResult(false);
    } catch (err) {
      setError(err.message || 'Re-grade failed');
    } finally {
      setLoading(false);
      setEvalStage('');
    }
  };

  const saveOverride = async (q) => {
    if (!meta.resultId) return;
    const draft = overrideDraft[q.id] ?? q.score;
    setSavingOverride(true);
    try {
      const updated = await patchQuestionScore(meta.resultId, q.regionIndex ?? 0, { awardedMarks: Number(draft) });
      applyResult(updated, sessionRef.current);
      setOverrideDraft((prev) => {
        const next = { ...prev };
        delete next[q.id];
        return next;
      });
    } catch (err) {
      setError(err.message || 'Could not save override');
    } finally {
      setSavingOverride(false);
    }
  };

  const activeQuestion = questions.find((q) => q.active) || questions[0];
  const activeRegionIndex = activeQuestion?.regionIndex ?? 0;

  const selectQuestion = (idx) => {
    setQuestions((prev) => {
      const q = prev[idx];
      const regionMeta = questionRegions.find(
        (item) => (item.region_index ?? item.question_index) === (q?.regionIndex ?? idx)
          || String(item.question_id) === String(q?.questionId),
      );
      if (regionMeta?.page_start) {
        setPreviewPage(Number(regionMeta.page_start));
      }
      return prev.map((item, i) => ({ ...item, active: i === idx }));
    });
  };

  const zoomIn = () => {
    const nz = Math.min(zoom + 0.15, 2);
    setZoom(nz);
    if (pageRef.current) {
      pageRef.current.style.transform = `scale(${nz})`;
      pageRef.current.style.transformOrigin = 'top center';
    }
  };

  const zoomOut = () => {
    const nz = Math.max(zoom - 0.15, 0.5);
    setZoom(nz);
    if (pageRef.current) {
      pageRef.current.style.transform = `scale(${nz})`;
      pageRef.current.style.transformOrigin = 'top center';
    }
  };

  return (
    <div className="app-shell portal-dark">
      <Sidebar />

      <div className="main-content" style={{ overflow: 'hidden' }}>
        <header className="topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.125rem', fontWeight: 700, color: '#ffffff' }}>Review grades</span>
            {meta.examId && (
              <span className="chip chip-neutral">{formatExamName(meta.examId)}</span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/processing')}>New paper</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={handleRegrade} disabled={loading || !meta.sheetId}>
              Re-grade
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate('/reports')}>Reports</button>
          </div>
        </header>

        {staleResult && !loading && (
          <div style={{ padding: '0.75rem 1.5rem', background: '#fffbeb', color: '#92400e', fontSize: '0.875rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
            <span>Marking scheme or answer layout changed — re-grade recommended for accurate OCR.</span>
            <button type="button" className="btn btn-secondary btn-sm" onClick={handleRegrade}>Re-grade now</button>
          </div>
        )}

        {error && (
          <div style={{ padding: '0.75rem 1.5rem', background: '#fef2f2', color: '#b91c1c', fontSize: '0.875rem' }}>
            {error}
          </div>
        )}

        {loading && (
          <div style={{ padding: '0.75rem 1.5rem', background: '#eff6ff', color: 'var(--primary)', fontSize: '0.875rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: evalStage ? '0.5rem' : 0 }}>
              <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>hourglass_top</span>
              <span>
                {evalStage || 'Grading in progress'} — large exams can take 5–10 minutes.
                {loadingSeconds > 0 && ` (${formatElapsed(loadingSeconds)} elapsed)`}
              </span>
            </div>
            {evalProgress > 0 && (
              <div className="progress" style={{ marginTop: '0.35rem' }}>
                <div className="progress-fill" style={{ width: `${evalProgress}%` }} />
              </div>
            )}
          </div>
        )}

        <div className="eval-shell">
          <div className="doc-panel">
            <div className="doc-toolbar">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span className="material-symbols-outlined" style={{ color: 'var(--primary)' }}>description</span>
                <div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 700 }}>{meta.filename || 'Answer sheet'}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>
                    {meta.examId ? formatExamName(meta.examId) : 'Student submission'}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.25rem' }}>
                {sheetPreviewUrl && (
                  <a
                    className="btn btn-ghost btn-sm"
                    href={sheetPreviewUrl}
                    target="_blank"
                    rel="noreferrer"
                    style={{ textDecoration: 'none' }}
                  >
                    Open full PDF
                  </a>
                )}
                <button type="button" className="icon-btn" title="Zoom in" onClick={zoomIn}><span className="material-symbols-outlined">zoom_in</span></button>
                <button type="button" className="icon-btn" title="Zoom out" onClick={zoomOut}><span className="material-symbols-outlined">zoom_out</span></button>
              </div>
            </div>

            <div className="doc-scroll">
              <div className="doc-page" ref={pageRef}>
                <SheetPreview
                  sheetId={meta.sheetId}
                  pdfUrl={sheetPreviewUrl}
                  filename={meta.filename}
                  activeRegionIndex={activeRegionIndex}
                  activeQuestionId={activeQuestion?.questionId || ''}
                  regionsPerPage={meta.regionsPerPage}
                  questionRegions={questionRegions}
                  previewPage={previewPage}
                  onPreviewPageChange={setPreviewPage}
                  refreshKey={previewRefresh}
                />
              </div>
            </div>
          </div>

          <div className="eval-panel">
            <div className="eval-header">
              <h1 style={{ fontSize: '0.9375rem', fontWeight: 700 }}>Scores by question</h1>
              {totalMax > 0 && (
                <span className="chip chip-info">{totalScore} / {totalMax}</span>
              )}
            </div>

            <div className="eval-scroll">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {questions.map((q, i) => (
                  <div
                    key={`${q.id}-${i}`}
                    className={`q-card${q.active ? ' active' : ''}`}
                    onClick={() => selectQuestion(i)}
                  >
                    <div className="q-card-header">
                      <div className="q-card-title-wrap">
                        <span className="q-badge" style={{ background: q.active ? 'var(--primary)' : '#f1f5f9', color: q.active ? '#fff' : '#475569' }}>{q.questionId || q.id}</span>
                        <span className="q-card-title">{truncate(q.prompt) || `Question ${q.questionId || q.id}`}</span>
                        {q.pageLabel && (
                          <span style={{ fontSize: '0.6875rem', color: 'var(--outline)', marginLeft: '0.35rem' }}>
                            · {q.pageLabel}
                          </span>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                        {q.confidence > 0 && (
                          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: confColor(q.confidence) }}>{q.confidence}% read confidence</span>
                        )}
                        <span style={{ fontSize: '1.125rem', fontWeight: 800 }}>{q.score}</span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>/ {q.maxScore}</span>
                      </div>
                    </div>

                    {q.active && (
                      <div className="q-body">
                        {q.pageLabel && (
                          <p style={{ fontSize: '0.75rem', color: 'var(--primary)', fontWeight: 600, margin: '0 0 0.5rem' }}>
                            Answer on {q.pageLabel.toLowerCase()} — highlighted on the sheet preview
                          </p>
                        )}
                        {q.prompt && (
                          <div className="q-prompt-box">
                            <p>{q.prompt}</p>
                          </div>
                        )}
                        <div className="q-cols">
                          <div>
                            <label style={{ fontSize: '0.5625rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--outline)', display: 'block', marginBottom: '0.5rem' }}>
                              Student answer (OCR from sheet){formatTextLabel(q.recognized)}
                            </label>
                            <div className="q-text-box q-text-box-scroll">
                              {q.recognized?.trim()
                                ? q.recognized.split('\n').map((line, li) => <span key={li}>{line}<br /></span>)
                                : <span style={{ color: 'var(--outline)' }}>No handwriting was detected in this answer region.</span>}
                            </div>
                            {cleanedDiffersFromOcr(q.recognized, q.formatted) && (
                              <div style={{ marginTop: '0.5rem' }}>
                                <label style={{ fontSize: '0.5625rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--outline)', display: 'block', marginBottom: '0.25rem' }}>
                                  Cleaned for grading{formatTextLabel(q.formatted)}
                                </label>
                                <div className="q-text-box q-text-box-scroll" style={{ opacity: 0.85, fontSize: '0.8125rem' }}>
                                  {q.formatted.split('\n').map((line, li) => <span key={li}>{line}<br /></span>)}
                                </div>
                              </div>
                            )}
                          </div>
                          <div>
                            <label style={{ fontSize: '0.5625rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--outline)', display: 'block', marginBottom: '0.5rem' }}>Feedback</label>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                              {q.points.length ? q.points.map((p, pi) => (
                                <div key={pi} className={`eval-point ${p.ok ? 'pass' : 'fail'}`}>
                                  <span className="material-symbols-outlined">{p.ok ? 'check_circle' : 'error'}</span>
                                  <span>{p.text}</span>
                                </div>
                              )) : (
                                <p style={{ fontSize: '0.8125rem', color: 'var(--outline)' }}>{q.feedback || 'No rubric data'}</p>
                              )}
                            </div>
                          </div>
                        </div>
                        {q.maxScore > 0 && (
                          <div className="progress"><div className="progress-fill" style={{ width: `${Math.round(q.score / q.maxScore * 100)}%` }} /></div>
                        )}
                        {hitlEnabled && q.maxScore > 0 && (
                          <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <label htmlFor={`override-score-${q.id}`} style={{ fontSize: '0.75rem', fontWeight: 600 }}>Override score</label>
                            <input
                              id={`override-score-${q.id}`}
                              type="number"
                              min={0}
                              max={q.maxScore}
                              step={0.5}
                              className="form-input"
                              style={{ width: 72 }}
                              value={overrideDraft[q.id] ?? q.score}
                              onChange={(e) => setOverrideDraft((prev) => ({ ...prev, [q.id]: e.target.value }))}
                              onClick={(e) => e.stopPropagation()}
                            />
                            <button type="button" className="btn btn-secondary btn-sm" disabled={savingOverride}
                              onClick={(e) => { e.stopPropagation(); saveOverride(q); }}>
                              Save override
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="eval-footer">
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/processing')}>Grade another</button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.5rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--outline)' }}>Total score</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--primary)' }}>{totalScore} / {totalMax}</div>
                </div>
                <button type="button" className="btn btn-primary" onClick={() => navigate('/reports')} disabled={!meta.resultId}>
                  Download report
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
