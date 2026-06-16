import { useState, useEffect } from 'react';
import AppShell from '../components/AppShell';
import { checkApiHealth, getResults, getSheets, getExams, reportPdfUrl } from '../lib/api';
import { formatExamName } from '../lib/examLabels';

function scoreColor(s) {
  if (s >= 76) return '#16a34a';
  if (s >= 41) return '#d97706';
  return '#dc2626';
}

function bandFromScore(pct) {
  if (pct > 75) return { label: 'Strong', chipClass: 'chip-success' };
  if (pct > 40) return { label: 'Fair', chipClass: 'chip-warning' };
  return { label: 'Needs review', chipClass: 'chip-error' };
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return String(iso);
  }
}

export default function ReportsPage() {
  const [reports, setReports] = useState([]);
  const [resultsCount, setResultsCount] = useState('');
  const [scoreFilter, setScoreFilter] = useState('All scores');
  const [examFilter, setExamFilter] = useState('');
  const [exams, setExams] = useState([]);
  const [allReports, setAllReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const ok = await checkApiHealth();
      if (!ok) {
        setResultsCount('Unable to load reports right now');
        setLoading(false);
        return;
      }

      const [results, sheets, examList] = await Promise.all([
        getResults({ limit: 50 }),
        getSheets(),
        getExams(),
      ]);
      if (Array.isArray(examList)) setExams(examList);

      if (!Array.isArray(results) || results.length === 0) {
        setReports([]);
        setAllReports([]);
        setResultsCount('No graded papers yet');
        setLoading(false);
        return;
      }

      const sheetById = {};
      if (Array.isArray(sheets)) {
        for (const s of sheets) sheetById[s.id] = s;
      }

      const mapped = results.map((r) => {
        const sheet = sheetById[r.sheet_id];
        const pct = r.max_total > 0 ? Math.round((r.total_marks / r.max_total) * 100) : 0;
        const { label, chipClass } = bandFromScore(pct);
        return {
          id: r.id,
          examId: r.exam_id,
          name: sheet?.filename || 'Graded paper',
          exam: formatExamName(r.exam_id),
          date: formatDate(r.created_at),
          score: pct,
          band: label,
          bandClass: chipClass,
          marks: `${r.total_marks} / ${r.max_total}`,
        };
      });

      setAllReports(mapped);
      setReports(mapped);
      setResultsCount(`${mapped.length} graded paper${mapped.length === 1 ? '' : 's'}`);
      setLoading(false);
    })();
  }, []);

  const applyFilters = () => {
    let filtered = [...allReports];
    if (scoreFilter === 'Needs review (below 40%)') filtered = filtered.filter((r) => r.score <= 40);
    if (scoreFilter === 'Fair (40–75%)') filtered = filtered.filter((r) => r.score > 40 && r.score <= 75);
    if (scoreFilter === 'Strong (above 75%)') filtered = filtered.filter((r) => r.score > 75);
    if (examFilter) filtered = filtered.filter((r) => r.examId === examFilter);
    setReports(filtered);
    setResultsCount(`Showing ${filtered.length} of ${allReports.length}`);
  };

  const downloadReport = (resultId) => {
    if (!resultId) return;
    window.open(reportPdfUrl(resultId), '_blank', 'noopener');
  };

  return (
    <AppShell title="Reports" showStatus>
      <div className="page-wrapper">
        <header style={{ marginBottom: '2rem' }} className="fade-in-up">
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Grade reports</h2>
          <p style={{ color: 'var(--on-surface-variant)', marginTop: '0.375rem', maxWidth: 480 }}>
            Download PDF summaries of completed gradings. Share them with students or keep them for your records.
          </p>
        </header>

        <div className="filter-bar">
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label" htmlFor="reports-exam-filter">Exam</label>
            <select id="reports-exam-filter" className="form-select" value={examFilter} onChange={(e) => setExamFilter(e.target.value)}>
              <option value="">All exams</option>
              {exams.map((e) => (
                <option key={e.id} value={e.id}>{formatExamName(e.id)}</option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label" htmlFor="reports-score-filter">Filter by performance</label>
            <select id="reports-score-filter" className="form-select" value={scoreFilter} onChange={(e) => setScoreFilter(e.target.value)}>
              <option>All scores</option>
              <option>Needs review (below 40%)</option>
              <option>Fair (40–75%)</option>
              <option>Strong (above 75%)</option>
            </select>
          </div>
          <div style={{ alignSelf: 'flex-end' }}>
            <button type="button" className="btn btn-secondary" onClick={applyFilters}>Apply</button>
          </div>
        </div>

        <div className="card" style={{ overflow: 'hidden', marginTop: '1.5rem' }}>
          <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontWeight: 700, margin: 0 }}>Graded papers</h3>
            <span style={{ fontSize: '0.875rem', color: 'var(--outline)' }}>{resultsCount}</span>
          </div>

          {loading ? (
            <p style={{ padding: '2rem', textAlign: 'center', color: 'var(--outline)' }}>Loading reports…</p>
          ) : reports.length === 0 ? (
            <div style={{ padding: '3rem 2rem', textAlign: 'center' }}>
              <span className="material-symbols-outlined" style={{ fontSize: '2.5rem', color: 'var(--outline)', marginBottom: '0.75rem' }}>description</span>
              <p style={{ fontWeight: 600, marginBottom: '0.375rem' }}>No reports yet</p>
              <p style={{ fontSize: '0.875rem', color: 'var(--outline)' }}>Grade a paper first — your PDF reports will show up here.</p>
            </div>
          ) : (
            reports.map((r) => (
              <div key={r.id} className="report-row" style={{ display: 'grid', gridTemplateColumns: '1fr 120px 100px 80px', gap: '1rem', alignItems: 'center', padding: '1rem 1.5rem', borderBottom: '1px solid #f1f5f9' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{r.name}</div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--outline)' }}>{r.exam} · {r.date}</div>
                </div>
                <span className="chip chip-neutral">{r.marks}</span>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontWeight: 700, color: scoreColor(r.score) }}>{r.score}%</div>
                  <span className={`chip ${r.bandClass}`} style={{ fontSize: '0.625rem', marginTop: '0.25rem' }}>{r.band}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => downloadReport(r.id)} title="Download PDF">
                    <span className="material-symbols-outlined">download</span>
                    PDF
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </AppShell>
  );
}
