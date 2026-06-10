import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { apiFetch } from '../lib/api';

const INITIAL_QUESTIONS = [
  {
    id: 'Q2',
    title: 'Kinetic Energy Derivation',
    confidence: 94,
    score: 8,
    maxScore: 10,
    active: true,
    recognized: 'W = ∫ F dx = ∫ ma dx\nW = m ∫ (dv/dt) dx = m ∫ v dv\nW = 1/2 mv² − 1/2 mv₀²\n... final result: 124.5 Joules',
    points: [
      { ok: true,  text: 'Correct integral setup' },
      { ok: true,  text: 'Work-Energy theorem used' },
      { ok: false, text: 'Calculation error in step 3 (−2 pts)' },
    ],
  },
  { id: 'Q1', title: 'Basic Kinematics Definitions',  confidence: 100, score: 5,  maxScore: 5,  active: false },
  { id: 'Q3', title: 'Vector Summation Graphic',       confidence: 82,  score: 12, maxScore: 15, active: false },
  { id: 'Q4', title: 'Thermodynamics — First Law',     confidence: 89,  score: 9,  maxScore: 10, active: false },
];

function confColor(c) {
  return c >= 90 ? '#22c55e' : c >= 75 ? '#f97316' : '#ef4444';
}

export default function EvaluatorPage() {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState(INITIAL_QUESTIONS);
  const [zoom, setZoom] = useState(1);
  const [activeOverlay, setActiveOverlay] = useState(2);
  const [submitState, setSubmitState] = useState('idle'); // 'idle' | 'submitting' | 'done'
  const pageRef = useRef(null);

  const totalScore = questions.reduce((a, q) => a + q.score, 0);
  const totalMax = questions.reduce((a, q) => a + q.maxScore, 0);

  const selectQuestion = (idx) => {
    setQuestions(prev => prev.map((q, i) => ({ ...q, active: i === idx })));
    const qId = questions[idx].id.replace('Q', '');
    setActiveOverlay(parseInt(qId));
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

  const submitScore = async () => {
    setSubmitState('submitting');
    try {
      await apiFetch('/submit-grade', {
        method: 'POST',
        body: JSON.stringify({ paper_id: 'Physics_Midterm_Paper_042', total: totalScore, max: totalMax }),
      });
    } catch {}
    setSubmitState('done');
    setTimeout(() => navigate('/reports'), 1200);
  };

  const OVERLAYS = [
    { q: 1, style: { top: '12%', left: '10%', width: '80%', height: '15%' } },
    { q: 2, style: { top: '28%', left: '10%', width: '80%', height: '25%' } },
    { q: 3, style: { top: '55%', left: '10%', width: '80%', height: '18%' } },
    { q: 4, style: { top: '75%', left: '10%', width: '80%', height: '18%' } },
  ];

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="main-content" style={{ overflow: 'hidden' }}>
        {/* Topbar */}
        <header className="topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.125rem', fontWeight: 700, color: '#0f172a' }}>GRADE</span>
            <nav style={{ display: 'flex', gap: '1.5rem', marginLeft: '1rem' }}>
              {[['Features', '/'], ['Solutions', '#'], ['Documentation', '#']].map(([label, href]) => (
                <a
                  key={label}
                  href={href}
                  style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--on-surface-variant)', transition: 'color var(--transition)' }}
                  onMouseOver={e => e.target.style.color = 'var(--primary)'}
                  onMouseOut={e => e.target.style.color = 'var(--on-surface-variant)'}
                >
                  {label}
                </a>
              ))}
            </nav>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/dashboard')}>Login</button>
            <button className="btn btn-primary btn-sm" style={{ background: 'var(--primary-container)' }} onClick={() => navigate('/upload')}>Get Started</button>
          </div>
        </header>

        <div className="eval-shell">

          {/* ── Left: Scanned Document ── */}
          <div className="doc-panel">
            <div className="doc-toolbar">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span className="material-symbols-outlined" style={{ color: 'var(--primary)' }}>description</span>
                <div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 700 }}>Physics_Midterm_Paper_042.pdf</div>
                  <div style={{ fontSize: '0.625rem', color: 'var(--outline)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Page 1 of 3 · Scanned @ 300DPI</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.25rem' }}>
                <button className="icon-btn" title="Zoom in" id="btn-zoom-in" onClick={zoomIn}><span className="material-symbols-outlined">zoom_in</span></button>
                <button className="icon-btn" title="Zoom out" id="btn-zoom-out" onClick={zoomOut}><span className="material-symbols-outlined">zoom_out</span></button>
                <button className="icon-btn" title="Fit" onClick={() => { setZoom(1); if (pageRef.current) pageRef.current.style.transform = ''; }}><span className="material-symbols-outlined">fit_screen</span></button>
              </div>
            </div>

            <div className="doc-scroll">
              <div className="doc-page" ref={pageRef}>
                <img
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuCHjlYxI_uc-aX-aEpLvehOghI6Jlu80qIdHl-GJs7W2nBaq_VgVaaH4gIlLYkzGgCq1pRBHpszDgfElxzeQ8QSd-_kzvsPyxSuFdYWNEQ5FyblJ7NMjt6AWBn4kTodCLbOevflf2dhRDoXQrx7uLGx4D_CrL1N3rcQC9xdcRGoDKSkSv4U0Neuqyc-8eg0j1DQmffwBDH-lxHnPaGhkctQ6pfGl77K2oif2kjXZXRXXdHCPUHaqkOUafjTygt5OjdvGrjct8m3v2k"
                  alt="Handwritten physics exam paper with AI bounding boxes"
                />
                {OVERLAYS.map(({ q, style }) => (
                  <div
                    key={q}
                    className={`scanned-overlay${activeOverlay === q ? ' active' : ''}`}
                    style={style}
                    title={`Question ${q} Block`}
                    onClick={() => setActiveOverlay(q)}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* ── Right: Evaluation Details ── */}
          <div className="eval-panel">
            <div className="eval-header">
              <h1 style={{ fontSize: '0.9375rem', fontWeight: 700 }}>AI Evaluation Breakdown</h1>
              <span className="chip chip-info" style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <span className="material-symbols-outlined" style={{ fontSize: '0.875rem', fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                AI CONFIDENCE: 98.4%
              </span>
            </div>

            <div className="eval-scroll">
              {/* Summary Insight */}
              <section style={{ background: 'var(--surface-container-lowest)', padding: '1.25rem', borderRadius: 'var(--radius-lg)', border: '1px solid rgba(0,88,190,0.12)', boxShadow: 'var(--shadow-sm)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.625rem' }}>
                  <span className="material-symbols-outlined" style={{ color: 'var(--primary)', fontSize: '1rem' }}>psychology</span>
                  <span style={{ fontSize: '0.625rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)' }}>Summary Insight</span>
                </div>
                <p style={{ fontSize: '0.875rem', color: 'var(--on-surface-variant)', lineHeight: 1.6 }}>
                  Excellent derivation of the formula in Question 2, but a calculation error in step 3 led to a cascading inaccuracy in the final result. The conceptual understanding remains high.
                </p>
              </section>

              {/* Question list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {questions.map((q, i) => (
                  <div
                    key={q.id}
                    className={`q-card${q.active ? ' active' : ''}`}
                    onClick={() => selectQuestion(i)}
                  >
                    <div className="q-card-header">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <span className="q-badge" style={{ background: q.active ? 'var(--primary)' : '#f1f5f9', color: q.active ? '#fff' : '#475569' }}>{q.id}</span>
                        <span style={{ fontSize: '0.875rem', fontWeight: 700 }}>{q.title}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: '0.5625rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--outline)', fontWeight: 700 }}>Confidence</div>
                          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: confColor(q.confidence) }}>{q.confidence}%</div>
                        </div>
                        <div style={{ width: 1, height: '2rem', background: '#f1f5f9' }} />
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                          <span style={{ fontSize: '1.125rem', fontWeight: 800 }}>{q.score}</span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>/ {q.maxScore}</span>
                          <button className="icon-btn" title="Edit score" style={{ width: '1.75rem', height: '1.75rem', color: 'var(--outline)' }}>
                            <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>edit</span>
                          </button>
                        </div>
                      </div>
                    </div>

                    {q.active && q.recognized && (
                      <div className="q-body">
                        <div className="q-cols">
                          <div>
                            <label style={{ fontSize: '0.5625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--outline)', display: 'block', marginBottom: '0.5rem' }}>Recognized Text</label>
                            <div className="q-text-box">{q.recognized.split('\n').map((line, li) => <span key={li}>{line}<br /></span>)}</div>
                          </div>
                          <div>
                            <label style={{ fontSize: '0.5625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--outline)', display: 'block', marginBottom: '0.5rem' }}>Evaluation Logic</label>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                              {q.points.map((p, pi) => (
                                <div key={pi} className={`eval-point ${p.ok ? 'pass' : 'fail'}`}>
                                  <span className="material-symbols-outlined">{p.ok ? 'check_circle' : 'error'}</span>
                                  <span>{p.text}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                        <div className="progress"><div className="progress-fill" style={{ width: `${Math.round(q.score / q.maxScore * 100)}%` }} /></div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="eval-footer">
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button className="btn btn-secondary btn-sm">
                  <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>chevron_left</span>
                  Previous Paper
                </button>
                <button className="btn btn-secondary btn-sm">
                  Next Paper
                  <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>chevron_right</span>
                </button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.5rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--outline)' }}>Total Grade</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--primary)' }}>{totalScore} / {totalMax}</div>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={submitScore}
                  disabled={submitState !== 'idle'}
                  style={submitState === 'done' ? { background: '#22c55e' } : { background: 'var(--primary-container)' }}
                >
                  {submitState === 'submitting' ? 'Submitting…' : submitState === 'done' ? '✓ Score Submitted' : 'Submit Final Score'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
