import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AppShell from '../components/AppShell';
import { useApiStatus } from '../hooks/useApiStatus';
import { formatExamName } from '../lib/examLabels';
import { hintForExam, hintForKeyCount } from '../lib/examLayouts';
import { pollJob, stageLabel } from '../lib/jobs';
import {
  createUploadBundleJob,
  createUploadSheetJob,
  createEvaluateJob,
  saveGradeSession,
  parseRegionsSum,
  parseRegionsPerPage,
  getExams,
  getExamQuestionPrompts,
  getExamQuestionCount,
  getJob,
  GRADE_SESSION,
  sheetPreviewImageUrl,
} from '../lib/api';

function formatBytes(b) {
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

function friendlyUploadError(message) {
  const m = String(message || '');
  if (m.includes('.json or text-based .pdf') || m.includes('.json, .docx')) {
    return 'The marking scheme must be a Word file (.docx). If you already use .docx, restart the grading service (API) and try again.';
  }
  if (m.includes('DOCX') || m.includes('Invalid or empty DOCX')) {
    return 'Could not read the marking scheme. Please upload a valid Word (.docx) answer key.';
  }
  if (m.includes('exam_id')) {
    return 'Please select or enter an exam / subject name.';
  }
  if (m.includes('Missing filename')) {
    return 'One of the files could not be read. Try choosing the file again.';
  }
  return m || 'Upload failed. Please check both files and try again.';
}

function validateUploadFiles(keyFile, sheetFile, mode) {
  if (mode !== 'sheet_only' && keyFile) {
    const keyName = (keyFile?.name || '').toLowerCase();
    if (!/\.(docx|json|pdf)$/.test(keyName)) {
      return 'Marking scheme must be a Word (.docx) or JSON file.';
    }
  }
  if (sheetFile) {
    const sheetName = (sheetFile?.name || '').toLowerCase();
    if (!/\.(pdf|png|jpe?g|tiff?)$/.test(sheetName)) {
      return 'Answer sheet must be a PDF or image (PNG, JPEG).';
    }
  }
  return null;
}

function FileUploadSlot({
  step, title, description, formats, icon, accept, file, onFile, disabled,
}) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  return (
    <div className="card" style={{ padding: '1.5rem', opacity: disabled ? 0.65 : 1, display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
        <div style={{
          width: '2rem', height: '2rem', borderRadius: '50%', flexShrink: 0,
          background: file ? 'rgba(34, 197, 94, 0.15)' : 'rgba(99, 102, 241, 0.15)',
          color: file ? '#4ade80' : '#a5b4fc',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.875rem',
        }}>
          {file ? '✓' : step}
        </div>
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#ffffff', margin: 0 }}>{title}</h3>
          <p style={{ fontSize: '0.8125rem', color: '#94a3b8', margin: '0.25rem 0 0' }}>{description}</p>
        </div>
      </div>
      <div
        className={`upload-zone${dragOver ? ' drag-over' : ''}${file ? ' has-file' : ''}`}
        role="button"
        tabIndex={disabled ? -1 : 0}
        style={{
          margin: 0,
          padding: '2.5rem 1.5rem',
          minHeight: '160px',
          background: '#ffffff',
          border: dragOver ? '2px dashed #6366f1' : '2px dashed #c7d2fe',
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#1e293b',
          transition: 'all var(--transition)'
        }}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' && !disabled) inputRef.current?.click(); }}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={disabled ? undefined : onDrop}
      >
        <input ref={inputRef} type="file" accept={accept} style={{ display: 'none' }} disabled={disabled}
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
        <span className="material-symbols-outlined" style={{ fontSize: '2.25rem', color: file ? '#16a34a' : '#6366f1', marginBottom: '0.75rem' }}>
          {file ? 'task_alt' : (icon === 'key' ? 'vpn_key' : 'description')}
        </span>
        {file ? (
          <>
            <p style={{ fontWeight: 700, fontSize: '0.875rem', margin: '0 0 0.25rem', wordBreak: 'break-word', color: '#0f172a' }}>{file.name}</p>
            <p style={{ fontSize: '0.75rem', color: '#64748b', margin: 0 }}>{formatBytes(file.size)}</p>
            <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: '0.75rem', color: '#6366f1' }}
              onClick={(e) => { e.stopPropagation(); onFile(null); }}>Replace file</button>
          </>
        ) : (
          <>
            <p style={{ fontWeight: 700, fontSize: '0.875rem', margin: '0 0 0.25rem', color: '#0f172a' }}>Drop file here</p>
            <p style={{ fontSize: '0.75rem', color: '#64748b', margin: '0 0 1rem' }}>{formats}</p>
            <span className="btn btn-secondary btn-sm" style={{ background: '#ffffff', color: '#1e293b', border: '1px solid #cbd5e1', boxShadow: '0 1px 2px rgba(0,0,0,0.05)', fontWeight: 600 }}>Choose file</span>
          </>
        )}
      </div>
    </div>
  );
}

function RegionPreview({ sheetId }) {
  if (!sheetId) return null;
  return (
    <div className="card" style={{ padding: '1rem', marginTop: '1rem' }}>
      <p style={{ fontWeight: 700, fontSize: '0.8125rem', marginBottom: '0.5rem' }}>Segmentation preview</p>
      <img src={sheetPreviewImageUrl(sheetId)} alt="Answer regions" style={{ width: '100%', borderRadius: 8, border: '1px solid #e2e8f0' }} />
      <p style={{ fontSize: '0.75rem', color: 'var(--outline)', marginTop: '0.5rem' }}>Does the orange grid match your answer regions?</p>
    </div>
  );
}

export default function UploadPage() {
  const navigate = useNavigate();
  const [uploadMode, setUploadMode] = useState('bundle');
  const [examId, setExamId] = useState('');
  const [examSearch, setExamSearch] = useState('');
  const [exams, setExams] = useState([]);
  const [keyFile, setKeyFile] = useState(null);
  const [sheetFile, setSheetFile] = useState(null);
  const [batchFiles, setBatchFiles] = useState([]);
  const [batchQueue, setBatchQueue] = useState([]);
  const [regionsSpec, setRegionsSpec] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [step, setStep] = useState(1);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [previewSheetId, setPreviewSheetId] = useState('');
  const { apiOk, markConnected } = useApiStatus(0);

  useEffect(() => {
    (async () => {
      const list = await getExams();
      if (Array.isArray(list)) {
        setExams(list);
        markConnected();
        if (list.length && !examId) {
          const withKeys = list.find((e) => e.key_count > 0) || list[0];
          setExamId(withKeys.id);
          setUploadMode(withKeys.key_count > 0 ? 'sheet_only' : 'bundle');
        }
      }
    })();
  }, [markConnected]);

  useEffect(() => {
    const resolved = examId === '__new__' ? '' : examId;
    const preset = hintForExam(resolved);
    if (preset) {
      setRegionsSpec(preset);
      return;
    }
    const exam = exams.find((e) => e.id === resolved);
    if (exam?.key_count === 6) {
      const fromKeys = hintForKeyCount(exam.key_count);
      if (fromKeys) setRegionsSpec(fromKeys);
    }
  }, [examId, exams]);

  useEffect(() => {
    const storedJob = sessionStorage.getItem(GRADE_SESSION.jobId);
    if (!storedJob || uploading) return;
    (async () => {
      try {
        const job = await getJob(storedJob);
        if (job && (job.status === 'pending' || job.status === 'running')) {
          setUploading(true);
          setStep(2);
          await pollJob(storedJob, {
            onUpdate: (j) => {
              setProgress(j.progress || 0);
              setStatusText(stageLabel(j.stage));
              if (j.result?.sheet_id) setPreviewSheetId(j.result.sheet_id);
            },
          });
        }
      } catch {
        sessionStorage.removeItem(GRADE_SESSION.jobId);
      }
    })();
  }, []);

  const resolvedExamId = examId === '__new__' ? '' : examId;
  const selectedExam = exams.find((e) => e.id === resolvedExamId);

  const filteredExams = useMemo(() => {
    const q = examSearch.trim().toLowerCase();
    if (!q) return exams;
    return exams.filter((e) => e.id.toLowerCase().includes(q) || formatExamName(e.id).toLowerCase().includes(q));
  }, [exams, examSearch]);

  const storePrompts = async (ex) => {
    try {
      const prompts = await getExamQuestionPrompts(ex);
      if (prompts?.length) {
        sessionStorage.setItem(
          GRADE_SESSION.questionPrompts,
          JSON.stringify(Object.fromEntries(prompts.map((p) => [p.question_id, p.prompt]))),
        );
      }
    } catch { /* prompts load on evaluator */ }
  };

  const finishUpload = async (data, filename) => {
    const expectedNumRegions = parseRegionsSum(regionsSpec);
    saveGradeSession({
      examId: data.exam_id,
      sheetId: data.sheet_id,
      filename: filename || data.filename,
      expectedNumRegions: expectedNumRegions ?? undefined,
      regionsPerPage: parseRegionsPerPage(regionsSpec) ?? data.regions_per_page ?? undefined,
    });
    sessionStorage.removeItem(GRADE_SESSION.resultId);
    sessionStorage.removeItem(GRADE_SESSION.jobId);
    await storePrompts(data.exam_id);
    setProgress(100);
    setStatusText('Ready to grade');
    setTimeout(() => navigate('/evaluator'), 700);
  };

  const runUpload = useCallback(async () => {
    const ex = resolvedExamId.trim();
    if (!ex) {
      setError('Please choose or enter an exam / subject.');
      return;
    }
    if (uploadMode === 'bundle' && (!keyFile || !sheetFile)) {
      setError('Please upload both documents — marking scheme and answer sheet.');
      return;
    }
    if (uploadMode === 'sheet_only' && !sheetFile) {
      setError('Please upload an answer sheet.');
      return;
    }
    if (uploadMode === 'sheet_only' && selectedExam && selectedExam.key_count === 0) {
      setError('This exam has no marking scheme yet. Upload a full bundle or pick another exam.');
      return;
    }
    const fileErr = validateUploadFiles(keyFile, sheetFile, uploadMode);
    if (fileErr) {
      setError(fileErr);
      return;
    }
    if (apiOk === false) {
      setError('We could not reach the grading service. Please try again in a moment.');
      return;
    }

    const regions = parseRegionsPerPage(regionsSpec);
    if (regions && uploadMode === 'sheet_only') {
      const count = await getExamQuestionCount(ex);
      if (count?.question_count && parseRegionsSum(regionsSpec) !== count.question_count) {
        setError(`Layout sums to ${parseRegionsSum(regionsSpec)} regions but this exam has ${count.question_count} questions.`);
        return;
      }
    }

    setError('');
    setUploading(true);
    setStep(2);
    setProgress(5);
    setStatusText('Starting…');

    try {
      let job;
      if (uploadMode === 'bundle') {
        job = await createUploadBundleJob(ex, keyFile, sheetFile, { regionsPerPage: regionsSpec });
      } else {
        job = await createUploadSheetJob(ex, sheetFile, { regionsPerPage: regionsSpec });
      }
      sessionStorage.setItem(GRADE_SESSION.jobId, job.job_id);
      const finalJob = await pollJob(job.job_id, {
        onUpdate: (j) => {
          setProgress(j.progress || 0);
          setStatusText(stageLabel(j.stage));
          if (j.result?.sheet_id) setPreviewSheetId(j.result.sheet_id);
        },
      });
      if (finalJob.status === 'failed') throw new Error(finalJob.error || 'Upload failed');
      await finishUpload(finalJob.result, finalJob.result?.filename);
    } catch (err) {
      setError(friendlyUploadError(err.message));
      setUploading(false);
      setStep(1);
      setProgress(0);
      setStatusText('');
      sessionStorage.removeItem(GRADE_SESSION.jobId);
    }
  }, [apiOk, navigate, regionsSpec, keyFile, sheetFile, resolvedExamId, uploadMode, selectedExam]);

  const runBatch = useCallback(async () => {
    const ex = resolvedExamId.trim();
    if (!ex || !batchFiles.length) {
      setError('Select an exam and add answer sheets.');
      return;
    }
    if (selectedExam?.key_count === 0) {
      setError('This exam has no marking scheme. Upload keys first.');
      return;
    }
    setError('');
    setUploading(true);
    setStep(2);
    const regions = parseRegionsPerPage(regionsSpec);
    const queue = batchFiles.map((f, i) => ({
      id: `${f.name}-${i}`,
      filename: f.name,
      status: 'pending',
      sheetId: '',
      resultId: '',
      score: '',
    }));
    setBatchQueue(queue);

    for (let i = 0; i < batchFiles.length; i++) {
      const file = batchFiles[i];
      setBatchQueue((q) => q.map((row, idx) => idx === i ? { ...row, status: 'uploading' } : row));
      setStatusText(`Uploading ${file.name} (${i + 1}/${batchFiles.length})…`);
      try {
        const uploadJob = await createUploadSheetJob(ex, file, { regionsPerPage: regions });
        const uploadDone = await pollJob(uploadJob.job_id, {
          onUpdate: (j) => setProgress(Math.round(((i + (j.progress || 0) / 100) / batchFiles.length) * 50)),
        });
        if (uploadDone.status === 'failed') throw new Error(uploadDone.error);
        const sheetId = uploadDone.result?.sheet_id;
        setBatchQueue((q) => q.map((row, idx) => idx === i ? { ...row, status: 'grading', sheetId } : row));
        setStatusText(`Grading ${file.name}…`);
        let evalJobId = null;
        try {
          const evalJob = await createEvaluateJob(sheetId, ex, { regionsPerPage: regions });
          evalJobId = evalJob.job_id;
        } catch (err) {
          if (err.status === 409 && err.jobId) {
            evalJobId = err.jobId;
          } else {
            throw err;
          }
        }
        const evalDone = await pollJob(evalJobId, {
          onUpdate: (j) => setProgress(50 + Math.round(((i + (j.progress || 0) / 100) / batchFiles.length) * 50)),
        });
        if (evalDone.status === 'failed') throw new Error(evalDone.error);
        const result = evalDone.result;
        setBatchQueue((q) => q.map((row, idx) => idx === i ? {
          ...row,
          status: 'done',
          sheetId,
          resultId: result?.result_id,
          score: `${result?.total_marks ?? '—'} / ${result?.max_total ?? '—'}`,
        } : row));
      } catch (err) {
        setBatchQueue((q) => q.map((row, idx) => idx === i ? { ...row, status: 'error', score: err.message } : row));
      }
    }
    setProgress(100);
    setStatusText('Batch complete');
    setUploading(false);
  }, [batchFiles, resolvedExamId, regionsSpec, selectedExam]);

  const canSubmit = uploadMode === 'batch'
    ? batchFiles.length > 0 && resolvedExamId.trim() && !uploading && apiOk !== false
    : (uploadMode === 'sheet_only' ? sheetFile : keyFile && sheetFile) && resolvedExamId.trim() && !uploading && apiOk !== false;

  const showNewExamInput = exams.length === 0 || examId === '__new__' || (resolvedExamId && !exams.some((e) => e.id === resolvedExamId));

  return (
    <AppShell title="Grade new papers" showStatus>
      <div className="page-wrapper" style={{ color: '#f1f5f9' }}>
        <p style={{ color: '#94a3b8', marginBottom: '1.5rem', maxWidth: 560, lineHeight: 1.6 }}>
          Upload marking schemes and student answer sheets, or add sheets to an exam that already has keys.
        </p>

        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
          {[
            { id: 'bundle', label: 'New exam (key + sheet)' },
            { id: 'sheet_only', label: 'Existing exam (sheet only)' },
            { id: 'batch', label: 'Batch sheets' },
          ].map((m) => (
            <button key={m.id} type="button"
              className={`btn btn-sm ${uploadMode === m.id ? 'btn-grad' : ''}`}
              style={uploadMode === m.id ? { borderRadius: '8px' } : { borderRadius: '8px', background: '#ffffff', color: '#1e293b', border: '1px solid #cbd5e1' }}
              onClick={() => setUploadMode(m.id)} disabled={uploading}>
              {m.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 280px', gap: '2rem', alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div className="card" style={{ padding: '1.5rem' }}>
              {exams.length > 0 ? (
                <>
                  <label className="form-label" htmlFor="exam-select">Exam / subject</label>
                  <input
                    id="exam-search"
                    className="form-input"
                    placeholder="Search exams…"
                    value={examSearch}
                    onChange={(e) => setExamSearch(e.target.value)}
                    aria-label="Search exams"
                    style={{ width: '100%', marginBottom: '0.5rem' }}
                    disabled={uploading}
                  />
                  <select
                    id="exam-select"
                    className="form-select"
                    value={exams.some((e) => e.id === examId) ? examId : (examId === '__new__' ? '__new__' : '')}
                    onChange={(e) => setExamId(e.target.value)}
                    style={{ width: '100%', marginBottom: '0.5rem' }}
                    disabled={uploading}
                  >
                    <option value="">Select an exam…</option>
                    {filteredExams.map((e) => (
                      <option key={e.id} value={e.id}>
                        {formatExamName(e.id)} ({e.key_count} keys, {e.sheet_count} sheets)
                      </option>
                    ))}
                    <option value="__new__">+ New exam name</option>
                  </select>
                </>
              ) : (
                <>
                  <label className="form-label" htmlFor="exam-id">Exam / subject</label>
                  <input
                    id="exam-id"
                    className="form-input"
                    placeholder="e.g. cie-dm"
                    value={resolvedExamId}
                    onChange={(e) => setExamId(e.target.value)}
                    style={{ width: '100%' }}
                    disabled={uploading}
                  />
                </>
              )}
              {exams.length > 0 && showNewExamInput && (
                <>
                  <label className="form-label" htmlFor="exam-id-new" style={{ marginTop: '0.5rem' }}>
                    New exam name
                  </label>
                  <input
                    id="exam-id-new"
                    className="form-input"
                    placeholder="e.g. cie-dm"
                    value={examId === '__new__' ? '' : resolvedExamId}
                    onChange={(e) => setExamId(e.target.value)}
                    style={{ width: '100%' }}
                    disabled={uploading}
                  />
                </>
              )}
              {selectedExam && (
                <p style={{ fontSize: '0.75rem', color: 'var(--outline)', marginTop: '0.5rem' }}>
                  <Link to={`/exams/${encodeURIComponent(selectedExam.id)}`}>View exam details</Link>
                </p>
              )}
              <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: '0.75rem', padding: 0, fontSize: '0.8125rem' }}
                onClick={() => setShowAdvanced((v) => !v)}>
                {showAdvanced ? 'Hide' : 'Show'} advanced options
              </button>
              {showAdvanced && (
                <div style={{ marginTop: '0.75rem' }}>
                  <label className="form-label" htmlFor="regions-spec">Answer layout (comma-separated rows per page)</label>
                  <input id="regions-spec" className="form-input" placeholder="e.g. 3,1,1,1"
                    value={regionsSpec} onChange={(e) => setRegionsSpec(e.target.value)} style={{ width: '100%' }} disabled={uploading} />
                </div>
              )}
            </div>

            {uploadMode === 'batch' ? (
              <div className="card" style={{ padding: '1.25rem' }}>
                <label className="form-label" htmlFor="batch-sheets">Answer sheets (multiple)</label>
                <input
                  id="batch-sheets"
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.tiff"
                  disabled={uploading}
                  onChange={(e) => setBatchFiles(Array.from(e.target.files || []))}
                />
                {batchFiles.length > 0 && (
                  <p style={{ fontSize: '0.8125rem', marginTop: '0.5rem' }}>{batchFiles.length} file(s) selected</p>
                )}
                {batchQueue.length > 0 && (
                  <table style={{ width: '100%', fontSize: '0.8125rem', marginTop: '1rem' }}>
                    <thead><tr><th>File</th><th>Status</th><th>Score</th></tr></thead>
                    <tbody>
                      {batchQueue.map((row) => (
                        <tr key={row.id}>
                          <td>{row.filename}</td>
                          <td>{row.status}</td>
                          <td>{row.score}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
                {uploadMode === 'bundle' && (
                  <FileUploadSlot step={1} title="Marking scheme" description="Official answer key."
                    formats="Word (.docx) or JSON" icon="key" accept=".docx,.json,.pdf"
                    file={keyFile} onFile={setKeyFile} disabled={uploading} />
                )}
                <FileUploadSlot step={uploadMode === 'bundle' ? 2 : 1} title="Student answer sheet"
                  description={uploadMode === 'sheet_only' ? 'Uses existing keys for this exam.' : 'Scanned handwritten answers.'}
                  formats="PDF, PNG, or JPEG" icon="description" accept=".pdf,.png,.jpg,.jpeg,.tiff"
                  file={sheetFile} onFile={setSheetFile} disabled={uploading} />
              </div>
            )}

            {error && (
              <div style={{ padding: '0.75rem 1rem', background: '#fef2f2', color: '#b91c1c', borderRadius: 8, fontSize: '0.875rem' }}>{error}</div>
            )}

            {step >= 2 && (
              <div className="card" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ fontWeight: 700, margin: 0 }}>Working on it…</h3>
                  <span style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--primary)' }}>{progress}%</span>
                </div>
                <p style={{ fontSize: '0.875rem', color: 'var(--outline)', marginBottom: '0.5rem' }}>{statusText}</p>
                {progress < 100 && (
                  <p style={{ fontSize: '0.75rem', color: 'var(--outline)', marginBottom: '1rem' }}>
                    {progress < 50
                      ? 'Saving your file…'
                      : 'Handwriting is scanned when you grade — not during upload.'}
                  </p>
                )}
                <div className="progress" style={{ marginBottom: '1.25rem' }}>
                  <div className="progress-fill" style={{ width: `${progress}%` }} />
                </div>
                <RegionPreview sheetId={previewSheetId} />
              </div>
            )}
          </div>

          <aside style={{ position: 'sticky', top: '4.5rem' }}>
            <button type="button" className="btn btn-grad" style={{ width: '100%', padding: '1rem 1.5rem', fontSize: '1rem', borderRadius: '12px' }}
              disabled={!canSubmit}
              onClick={uploadMode === 'batch' ? runBatch : runUpload}>
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
              {uploading ? 'Please wait…' : uploadMode === 'batch' ? 'Start batch' : 'Start grading'}
            </button>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
