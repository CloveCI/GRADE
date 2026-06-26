import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../components/AppShell';
import { checkApiHealth, getMetricsOverview, getSheets } from '../lib/api';
import { formatExamName } from '../lib/examLabels';

const EMPTY_STATS = [
  { icon: 'history_edu', iconBg: '#eff6ff', iconColor: '#2563eb', badge: '—', badgeClass: 'chip-neutral', label: 'Papers graded', value: '—', barColor: '#2563eb', barW: '0%' },
  { icon: 'analytics', iconBg: '#fff7ed', iconColor: '#ea580c', badge: '—', badgeClass: 'chip-neutral', label: 'Class average', value: '—', barColor: '#f97316', barW: '0%' },
  { icon: 'pending_actions', iconBg: '#faf5ff', iconColor: '#9333ea', badge: '—', badgeClass: 'chip-neutral', label: 'Awaiting review', value: '—', barColor: null },
];

const EMPTY_UPLOADS = [
  { file: 'No papers yet', student: '—', date: '—', status: 'Pending', score: '—' },
];

const STATUS_MAP = {
  evaluated: 'chip-success',
  ingested: 'chip-info',
  Completed: 'chip-success',
  Graded: 'chip-success',
  Processing: 'chip-info',
  'In progress': 'chip-info',
  Failed: 'chip-error',
  Pending: 'chip-neutral',
};

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return String(iso);
  }
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(EMPTY_STATS);
  const [uploads, setUploads] = useState(EMPTY_UPLOADS);
  const [live, setLive] = useState(false);

  useEffect(() => {
    (async () => {
      const ok = await checkApiHealth();
      if (!ok) return;
      setLive(true);

      const [metrics, sheets] = await Promise.all([
        getMetricsOverview(),
        getSheets(),
      ]);

      if (metrics) {
        const avgPct = Math.round((metrics.avg_total_pct || 0) * 1000) / 10;
        const pending = Math.max(0, (metrics.sheets || 0) - (metrics.results || 0));
        setStats([
          {
            icon: 'history_edu', iconBg: '#eff6ff', iconColor: '#2563eb',
            badge: `${metrics.last_24h || 0} / 24h`, badgeClass: 'chip-success',
            label: 'Papers uploaded', value: String(metrics.sheets ?? 0),
            barColor: '#2563eb', barW: `${Math.min(100, (metrics.sheets || 0) * 5)}%`,
          },
          {
            icon: 'analytics', iconBg: '#fff7ed', iconColor: '#ea580c',
            badge: `${metrics.exams || 0} subjects`, badgeClass: 'chip-neutral',
            label: 'Class average', value: metrics.results ? `${avgPct}%` : '—',
            barColor: '#f97316', barW: `${avgPct}%`,
          },
          {
            icon: 'pending_actions', iconBg: '#faf5ff', iconColor: '#9333ea',
            badge: pending > 0 ? 'Action Required' : 'Up to date', badgeClass: pending > 0 ? 'chip-error' : 'chip-success',
            label: 'Awaiting review', value: String(pending),
            barColor: null,
          },
        ]);
      }

      if (Array.isArray(sheets) && sheets.length > 0) {
        setUploads(
          sheets.slice(0, 8).map((s) => ({
            file: s.filename || s.id,
            student: formatExamName(s.exam_id) || '—',
            date: formatDate(s.created_at),
            status: s.status === 'evaluated' ? 'Graded' : 'In progress',
            score: s.status === 'evaluated' ? 'Done' : '—',
          })),
        );
      } else if (live) {
        setUploads([{ file: 'No sheets yet', student: '—', date: '—', status: 'Pending', score: '—' }]);
      }
    })();
  }, []);

  return (
    <AppShell title="Dashboard" showStatus>
      <div className="page-wrapper">

        <section className="grid-3 fade-in-up" style={{ marginBottom: '2rem' }}>
          {stats.map((s) => (
            <div key={s.label} className="stat-card">
              <div className="stat-header">
                <div className="stat-icon" style={{ background: s.iconBg, color: s.iconColor }}>
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>{s.icon}</span>
                </div>
                <span className={`chip ${s.badgeClass}`}>{s.badge}</span>
              </div>
              <div className="stat-label">{s.label}</div>
              <div className="stat-value">{s.value}</div>
              {s.barColor ? (
                <div className="stat-bar"><div className="stat-bar-fill" style={{ width: s.barW, background: s.barColor }} /></div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginTop: '1rem', fontSize: '0.75rem', color: 'var(--outline)' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '0.875rem' }}>upload_file</span>
                  {live ? 'Upload a paper to get started' : 'Sign in when the service is available'}
                </div>
              )}
            </div>
          ))}
        </section>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
          <section className="card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '1.5rem', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>Recent Uploads</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--outline)', marginTop: 2 }}>
                  {live ? 'Your latest submissions' : 'Your activity will appear here'}
                </p>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/processing')}>New paper</button>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>File Name</th>
                    <th>Exam</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {uploads.map((r) => (
                    <tr key={r.file}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          <span className="material-symbols-outlined" style={{ color: 'var(--outline)' }}>description</span>
                          <span style={{ fontWeight: 500 }}>{r.file}</span>
                        </div>
                      </td>
                      <td style={{ color: 'var(--on-surface-variant)' }}>{r.student}</td>
                      <td style={{ color: 'var(--outline)', fontSize: '0.8125rem' }}>{r.date}</td>
                      <td><span className={`chip ${STATUS_MAP[r.status] || 'chip-neutral'}`}>{r.status}</span></td>
                      <td style={{ textAlign: 'right', fontWeight: 700, fontSize: '0.875rem' }}>{r.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a', marginBottom: '1rem' }}>Quick actions</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <button type="button" className="btn btn-primary" onClick={() => navigate('/processing')}>
                <span className="material-symbols-outlined">cloud_upload</span>
                Grade new papers
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => navigate('/evaluator')}>
                <span className="material-symbols-outlined">grading</span>
                Review scores
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => navigate('/reports')}>
                <span className="material-symbols-outlined">description</span>
                Download reports
              </button>
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
