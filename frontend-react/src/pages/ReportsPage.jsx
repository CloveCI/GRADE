import { useState, useEffect } from 'react';
import AppShell from '../components/AppShell';
import { apiFetch, checkApiHealth } from '../lib/api';

const REPORTS = [
  {
    thumb: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAaeH2u-lsSarlGbV_PDaPbwBHmcslhjr5WP7unp_w1NkEwAp3ih3Lny91zwe66FqZL1DJGODTpZQ0Mq9Xdjv3Y2f5Ojp77DDwTmQqcBsF4aSKlMfvk2gSPiZZ_4GIZLFx2WRzZ1MG1S3L_SFgyEJtR4LurbvjsaZYT_EACIlSNj9MKFeRAAdVoN-Sz_NSJh7A8TSzR2G8P344WPMpx8w6EXeDSmSRZ79qOIQRgJDwkaSAhgjn9qcB36BPZzSezPITESCJO8VhbXu4',
    name: 'Final_Thesis_Revision_V4.pdf', student: 'Alexander Thorne', date: 'Oct 12, 2023', course: 'CS101', score: 98, risk: 'Low Risk', riskClass: 'chip-success',
  },
  {
    thumb: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBZQ9VkyatwCYH4OTiQIGGZX1b44HzRp7n-ik5nIWnzGUr-eW7GB39TZnLmmsrL7WkB-TX3Vhc5JHj3BwUdRzkmnKACdbr1sDy3p-x7Zk-GUh0OrBCVFFdqtRMSVvgmVtVs2nT9P6p3LXfZv3dOSl6liGiyj4wAYjqxC6lT9VC8oYH3ODMoTNEto-2WMAGrZRoQX2PEliCHDLYY6vABPQi7vIdtM9b-awEX80ive4GJ6sFOV-CODlPKVRxekxcxbTavJ-bf3LL7QEM',
    name: 'Ethics_Essay_Submission.pdf', student: 'Marcus Vane', date: 'Oct 11, 2023', course: 'PHIL202', score: 32, risk: 'High Risk', riskClass: 'chip-error',
  },
  {
    thumb: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCe3Cuch_KwPrLYy1UgY89cfdmG5C0UqPvQOwaiYNMxIq9HQ0B43B2Dw8tzML5rkLVF2WSZ6qOn0odPoEibkBvHAo65AncplSjS6Hy3B46CA33by0Yb5p2TbBu7ksjEAPLk6cpr5DmC1sBZNWkq5up3n_g79-wkO4nCMy2Lyu8XyZZDbVXx5_lclDJ0S5vJcEaM0_qQGiLTZOpbtdWmzXnYp6-mLlX-ClNWw2b7qJ8RU5OFWnxz_d-p8gcO4DjEMPwjPVi1E8ntvks',
    name: 'Lab_Report_Organic_Chem.pdf', student: 'Sarah Jenkins', date: 'Oct 10, 2023', course: 'CHEM301', score: 67, risk: 'Moderate', riskClass: 'chip-warning',
  },
];

function scoreColor(s) {
  if (s >= 76) return '#16a34a';
  if (s >= 41) return '#d97706';
  return '#dc2626';
}

export default function ReportsPage() {
  const [reports, setReports] = useState(REPORTS);
  const [resultsCount, setResultsCount] = useState(`Showing ${REPORTS.length} of 1,420 results`);
  const [subjectFilter, setSubjectFilter] = useState('All Subjects');
  const [scoreFilter, setScoreFilter] = useState('All Scores');
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    (async () => {
      const ok = await checkApiHealth();
      if (ok) {
        const data = await apiFetch('/reports?limit=20');
        if (data?.reports) {
          setReports(data.reports);
          setResultsCount(`Showing ${data.reports.length} of ${data.total} results`);
        }
      }
    })();
  }, []);

  const applyFilters = () => {
    let filtered = [...REPORTS];
    if (scoreFilter === 'High Risk (0–40%)')  filtered = filtered.filter(r => r.score <= 40);
    if (scoreFilter === 'Moderate (41–75%)')  filtered = filtered.filter(r => r.score > 40 && r.score <= 75);
    if (scoreFilter === 'Low Risk (76–100%)') filtered = filtered.filter(r => r.score > 75);
    setReports(filtered);
    setResultsCount(`Showing ${filtered.length} of 1,420 results`);
  };

  const downloadReport = async (name) => {
    const data = await apiFetch(`/report/${encodeURIComponent(name)}`);
    if (data?.url) {
      window.open(data.url, '_blank');
    } else {
      alert(`Downloading ${name} (API offline — connect backend at localhost:8000)`);
    }
  };

  return (
    <AppShell title="Academic Reports" showStatus={false}>
      <div className="page-wrapper">

        {/* ── Page Header ── */}
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '2.5rem' }} className="fade-in-up">
          <div>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Academic Reports</h2>
            <p style={{ color: 'var(--on-surface-variant)', marginTop: '0.375rem', maxWidth: 480 }}>
              Review and download comprehensive integrity analysis for individual student submissions and batch evaluations.
            </p>
          </div>
          <button className="btn btn-secondary">
            <span className="material-symbols-outlined">share</span>
            Share Export
          </button>
        </header>

        {/* ── Filters ── */}
        <div className="filter-bar">
          <div className="form-group">
            <label className="form-label">Date Range</label>
            <div style={{ position: 'relative' }}>
              <span className="material-symbols-outlined" style={{ position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)', fontSize: '1.125rem', color: 'var(--outline)' }}>calendar_today</span>
              <select className="form-select" style={{ paddingLeft: '2.25rem' }}>
                <option>Last 30 Days</option>
                <option>Last Quarter</option>
                <option>Academic Year 2023-24</option>
                <option>Custom Range</option>
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Subject / Course</label>
            <div style={{ position: 'relative' }}>
              <span className="material-symbols-outlined" style={{ position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)', fontSize: '1.125rem', color: 'var(--outline)' }}>book</span>
              <select className="form-select" style={{ paddingLeft: '2.25rem' }} value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)}>
                <option>All Subjects</option>
                <option>Computer Science 101</option>
                <option>Advanced Ethics</option>
                <option>World History</option>
                <option>Physics</option>
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Score Range</label>
            <div style={{ position: 'relative' }}>
              <span className="material-symbols-outlined" style={{ position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)', fontSize: '1.125rem', color: 'var(--outline)' }}>analytics</span>
              <select className="form-select" style={{ paddingLeft: '2.25rem' }} value={scoreFilter} onChange={e => setScoreFilter(e.target.value)}>
                <option>All Scores</option>
                <option>High Risk (0–40%)</option>
                <option>Moderate (41–75%)</option>
                <option>Low Risk (76–100%)</option>
              </select>
            </div>
          </div>
          <div>
            <button className="btn" style={{ background: '#eff6ff', color: 'var(--primary)', fontWeight: 600, width: '100%', padding: '0.625rem 1rem' }} onClick={applyFilters}>
              Apply Filters
            </button>
          </div>
        </div>

        {/* ── Charts + Insight Row ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem', marginBottom: '2rem' }}>

          {/* Bar Chart */}
          <div className="card" style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>Batch Score Distribution</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--outline)', marginTop: 2 }}>Overview of 124 evaluated submissions in current filter</p>
              </div>
              <div style={{ display: 'flex', gap: '1rem' }}>
                {[['#22c55e', 'Passed'], ['#f59e0b', 'Warning'], ['#ef4444', 'Review']].map(([color, label]) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                    <span style={{ width: '0.625rem', height: '0.625rem', borderRadius: '50%', background: color, display: 'block' }} />
                    <span style={{ fontSize: '0.625rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--outline)' }}>{label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bar-chart">
              {[
                { tooltip: 'High Risk: 12%', height: '25%', bg: '#fecaca', label: '0–40%' },
                { tooltip: 'Moderate: 24%',  height: '45%', bg: '#fde68a', label: '41–75%' },
                { tooltip: 'Low Risk: 64%',  height: '95%', bg: '#bbf7d0', label: '76–100%' },
              ].map(({ tooltip, height, bg, label }) => (
                <div key={label} className="bar-col">
                  <div className="bar-tooltip">{tooltip}</div>
                  <div className="bar-fill" style={{ height, background: bg }} />
                  <div className="bar-label">{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* AI Insight Card */}
          <div className="insight-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              <span className="material-symbols-outlined" style={{ color: 'rgba(255,255,255,0.7)' }}>auto_awesome</span>
              <span style={{ fontSize: '0.625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'rgba(255,255,255,0.7)' }}>AI Intelligence Insight</span>
            </div>
            <h4 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '0.75rem', lineHeight: 1.4, position: 'relative', zIndex: 1 }}>
              Batch integrity improved by 14% compared to last semester.
            </h4>
            <p style={{ fontSize: '0.875rem', color: 'rgba(255,255,255,0.85)', lineHeight: 1.6, position: 'relative', zIndex: 1 }}>
              CS101 shows a notable decrease in high-risk citations. We recommend updating the citation workshop modules for incoming freshmen.
            </p>
            <button className="btn btn-sm" style={{ marginTop: '1.25rem', background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.25)', backdropFilter: 'blur(8px)', position: 'relative', zIndex: 1 }}>
              View Details
            </button>
          </div>
        </div>

        {/* ── Reports Table ── */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontWeight: 700, color: '#0f172a' }}>Recent Reports</h3>
            <span style={{ fontSize: '0.875rem', color: 'var(--outline)' }}>{resultsCount}</span>
          </div>

          {/* Table header */}
          <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr 100px 80px 100px', padding: '0.875rem 1.5rem', background: '#f8fafc', gap: '1rem', alignItems: 'center' }}>
            {['Preview', 'Report Details', 'Course', 'Score', 'Actions'].map((h, i) => (
              <span key={h} style={{ fontSize: '0.625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--outline)', textAlign: i >= 3 ? (i === 3 ? 'center' : 'right') : 'left' }}>{h}</span>
            ))}
          </div>

          {/* Report Rows */}
          {reports.map((r) => (
            <div key={r.name} className="report-row" style={{ display: 'grid', gridTemplateColumns: '80px 1fr 100px 80px 100px', gap: '1rem', alignItems: 'center' }}>
              <div className="report-thumb">
                <img src={r.thumb} alt={r.name} loading="lazy" />
                <div className="report-thumb-overlay">
                  <span className="material-symbols-outlined" style={{ color: '#fff', fontSize: '1.25rem' }}>visibility</span>
                </div>
              </div>
              <div>
                <div style={{ fontWeight: 600, color: '#0f172a', fontSize: '0.875rem' }}>{r.name}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>Student: {r.student} · {r.date}</div>
              </div>
              <span className="chip chip-neutral">{r.course}</span>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '0.875rem', fontWeight: 700, color: scoreColor(r.score) }}>{r.score}%</div>
                <div style={{ fontSize: '0.5625rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--outline)' }}>{r.risk}</div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.25rem' }}>
                <button className="icon-btn" title="Preview PDF" aria-label="Preview">
                  <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>zoom_in</span>
                </button>
                <button className="icon-btn" title="Download PDF" aria-label="Download" onClick={() => downloadReport(r.name)}>
                  <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>download</span>
                </button>
              </div>
            </div>
          ))}

          {/* Pagination */}
          <div className="pagination">
            <button className="btn btn-secondary btn-sm" disabled={currentPage === 1} onClick={() => setCurrentPage(p => Math.max(1, p - 1))}>Previous</button>
            <div style={{ display: 'flex', gap: '0.375rem' }}>
              {[1, 2, 3].map(n => (
                <button key={n} className={`page-btn${currentPage === n ? ' active' : ''}`} onClick={() => setCurrentPage(n)}>{n}</button>
              ))}
              <span style={{ padding: '0 0.5rem', color: 'var(--outline)', lineHeight: '2rem' }}>…</span>
              <button className="page-btn">59</button>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => setCurrentPage(p => p + 1)}>Next</button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
