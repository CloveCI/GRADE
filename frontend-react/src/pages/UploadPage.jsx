import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../components/AppShell';

function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
}

export default function UploadPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [files, setFiles] = useState([]);
  const [examId, setExamId] = useState('ID: #8821-EXAM');
  const [step, setStep] = useState(1);
  const [progress, setProgress] = useState(65);
  const [timeRemain, setTimeRemain] = useState('Approx. 45s remaining');
  const [processingFilename, setProcessingFilename] = useState('CS101_Final_SectionB.pdf');

  const animateProgress = useCallback((filename) => {
    setProcessingFilename(filename);
    let pct = 0;
    const iv = setInterval(() => {
      pct = Math.min(pct + Math.random() * 3, 100);
      setProgress(Math.round(pct));
      const secs = Math.max(0, Math.round((100 - pct) / 3));
      setTimeRemain(secs > 0 ? `Approx. ${secs}s remaining` : 'Finalizing…');
      if (pct >= 100) {
        clearInterval(iv);
        setTimeout(() => navigate('/evaluator'), 800);
      }
    }, 400);
  }, [navigate]);

  const handleFiles = useCallback(async (fileList) => {
    if (!fileList || fileList.length === 0) return;
    const arr = Array.from(fileList);
    setFiles(arr);
    setExamId(`Files: ${arr.length}`);
    setStep(2);

    const form = new FormData();
    arr.forEach(f => form.append('files', f));
    try {
      const res = await fetch('http://localhost:8000/process', { method: 'POST', body: form });
      if (res.ok) {
        const data = await res.json();
        console.info('[GRADE] Submitted to API:', data);
      }
    } catch { /* server not running — simulate */ }

    animateProgress(arr[0]?.name ?? 'document.pdf');
  }, [animateProgress]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const PIPELINE_STEPS = [
    { icon: 'check', state: 'done', status: 'COMPLETED', statusColor: '#22c55e', label: 'Segmentation', sub: '12 fields identified' },
    { icon: 'document_scanner', state: 'active', status: 'IN PROGRESS', statusColor: 'var(--primary)', label: 'OCR Recognition', sub: 'Handwriting analysis…' },
    { icon: 'grading', state: 'pending', status: 'QUEUED', statusColor: '#cbd5e1', label: 'Rubric Scoring', sub: 'Awaiting OCR data' },
  ];

  return (
    <AppShell title="Upload & Processing" showStatus={false} showFooter>
      <div className="page-wrapper">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '2rem', alignItems: 'start' }}>

          {/* Left Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

            {/* Upload Zone */}
            <div className="card" style={{ padding: 0 }}>
              <div
                className={`upload-zone${dragOver ? ' drag-over' : ''}`}
                id="drop-zone"
                role="button"
                aria-label="Upload files"
                tabIndex={0}
                style={{ margin: '1.5rem', borderRadius: 'var(--radius-lg)' }}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => { if (e.key === 'Enter') fileInputRef.current?.click(); }}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  id="file-input"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.tiff"
                  style={{ display: 'none' }}
                  onChange={(e) => handleFiles(e.target.files)}
                />
                <div className="upload-icon">
                  <span className="material-symbols-outlined">upload_file</span>
                </div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem', color: '#0f172a' }}>Upload Academic Documents</h3>
                <p style={{ color: 'var(--outline)', textAlign: 'center', maxWidth: 420, marginBottom: '1.5rem' }}>
                  Drag and drop PDF answer sheets or high-resolution images. AI will automatically segment and identify fields.
                </p>
                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                  <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>Select Files</button>
                  <button className="btn btn-secondary">Scan via Mobile</button>
                </div>
              </div>

              {/* File list */}
              {files.length > 0 && (
                <div style={{ padding: '0 1.5rem 1.5rem' }}>
                  <p style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--outline)', marginBottom: '0.75rem' }}>Queued Files</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {files.map((f) => (
                      <div key={f.name} className="file-list-item">
                        <span className="material-symbols-outlined" style={{ color: 'var(--outline)' }}>description</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, fontSize: '0.875rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>{formatBytes(f.size)}</div>
                        </div>
                        <span className="chip chip-info">Queued</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Processing Pipeline Card */}
            <div className="card" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
                <div>
                  <p style={{ fontSize: '0.625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--outline)' }}>Active Processing</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.25rem' }}>
                    <h3 style={{ fontSize: '1.375rem', fontWeight: 800, color: '#0f172a' }}>{processingFilename}</h3>
                    <span className="chip chip-info" style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <span className="material-symbols-outlined" style={{ fontSize: '0.75rem' }}>auto_awesome</span>
                      AI ACTIVE
                    </span>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--primary)' }}>{progress}%</span>
                  <p style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>{timeRemain}</p>
                </div>
              </div>

              <div className="progress" style={{ marginBottom: '2rem' }}>
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>

              <div className="pipeline-grid">
                {PIPELINE_STEPS.map((ps) => (
                  <div key={ps.label} className="pipeline-step">
                    <div className={`pipeline-step-icon ${ps.state}`}>
                      <span className="material-symbols-outlined">{ps.icon}</span>
                    </div>
                    <span style={{ fontSize: '0.625rem', fontWeight: 700, color: ps.statusColor, marginBottom: '0.25rem' }}>{ps.status}</span>
                    <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0f172a' }}>{ps.label}</span>
                    <p style={{ fontSize: '0.6875rem', color: 'var(--outline)', marginTop: '0.125rem' }}>{ps.sub}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: Preview + Insight */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', position: 'sticky', top: '4.5rem' }}>

            {/* Preview Panel */}
            <div className="card" style={{ overflow: 'hidden' }}>
              <div style={{ padding: '0.875rem 1rem', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#fafafa' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0f172a' }}>Live Preview</span>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button className="icon-btn" title="Zoom in"><span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>zoom_in</span></button>
                  <button className="icon-btn" title="Full screen"><span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>open_in_full</span></button>
                </div>
              </div>
              <div style={{ padding: '1rem' }}>
                <div className="preview-img-wrap">
                  <img
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuB-5hPjVvyN_eH-pP0fW2uj_Kf7AZ0g2GnRBApmV09ZHk3OmgQVoHqPnNkul0QI0lS24cIhre5vmUKReKYN34_pPhAKcXpyFrgJ4ZbhIbH04-lCj0ATTZnkvZBccryvnHw1NV8ZV3sJ3mUL-StvnFdEE2YhYAGrkJOLjA6SidKK_39RZSTmT_CDvRMJ-6GkY85Didn7nMWPRZetRIxPFu-g9YIEk17G5c5R2gWKTlcAyxbJtbBoKTBv0ZxgIqpeIF4IvvR9T2kG-Yk"
                    alt="Handwritten exam paper preview"
                  />
                  <div className="overlay-box" style={{ top: '8%', left: '5%', width: '90%', height: '12%' }}>NAME_FIELD (88%)</div>
                  <div className="overlay-box" style={{ top: '22%', left: '5%', width: '90%', height: '26%' }}>ANSWER_ZONE_01 (94%)</div>
                </div>

                <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {[['File size', '4.2 MB'], ['Page count', '1 of 12'], ['Resolution', '300 DPI']].map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                      <span style={{ color: 'var(--outline)' }}>{k}</span>
                      <span style={{ fontWeight: 600 }}>{v}</span>
                    </div>
                  ))}
                  <button className="btn btn-ghost" style={{ width: '100%', border: '2px solid rgba(0,88,190,0.15)', marginTop: '0.5rem' }}>Edit Mapping</button>
                </div>
              </div>
            </div>

            {/* AI Insight */}
            <div className="ai-panel">
              <div style={{ position: 'absolute', right: '-1rem', top: '-1rem', opacity: 0.08 }}>
                <span className="material-symbols-outlined" style={{ fontSize: '5rem', color: 'var(--primary)', fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
              </div>
              <div className="ai-panel-header">
                <span className="material-symbols-outlined">colors_spark</span>
                <span>AI Insight</span>
              </div>
              <p style={{ fontSize: '0.875rem', color: 'var(--on-surface-variant)', lineHeight: 1.6 }}>
                Handwriting clarity is rated as <strong style={{ color: '#1e40af' }}>High</strong>. OCR confidence for this student profile is typically <strong style={{ color: '#1e40af' }}>98.4%</strong>.
              </p>
            </div>

            {/* Submit button */}
            <button className="btn btn-primary" style={{ width: '100%', padding: '0.875rem' }} onClick={() => navigate('/evaluator')}>
              <span className="material-symbols-outlined">send</span>
              Submit for Evaluation
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
