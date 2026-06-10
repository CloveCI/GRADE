import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../components/AppShell';
import { checkApiHealth } from '../lib/api';

const STATS = [
  {
    icon: 'history_edu', iconBg: '#eff6ff', iconColor: '#2563eb',
    badge: '+12.5%', badgeClass: 'chip-success',
    label: 'Total Papers Processed', value: '12,450',
    barColor: '#2563eb', barW: '85%',
  },
  {
    icon: 'analytics', iconBg: '#fff7ed', iconColor: '#ea580c',
    badge: 'Avg. Month', badgeClass: 'chip-neutral',
    label: 'Average Score', value: '74.2%',
    barColor: '#f97316', barW: '74%',
  },
  {
    icon: 'pending_actions', iconBg: '#faf5ff', iconColor: '#9333ea',
    badge: 'Action Required', badgeClass: 'chip-error',
    label: 'Pending Evaluations', value: '18',
    barColor: null,
  },
];

const UPLOADS = [
  { file: 'Ethical_AI_v2.pdf',         student: 'Marcus Chen',    date: 'Oct 12, 10:45 AM', status: 'Completed', score: '92%'  },
  { file: 'Quantum_Thesis.docx',        student: 'Elena Rodriguez', date: 'Oct 12, 11:20 AM', status: 'Processing', score: '--'  },
  { file: 'History_Midterm.pdf',        student: 'Sarah Jenkins',  date: 'Oct 12, 09:15 AM', status: 'Failed',    score: 'ERR' },
  { file: 'MacroEcon_CaseStudy.pdf',    student: 'David Kim',      date: 'Oct 11, 04:30 PM', status: 'Completed', score: '78%'  },
];

const TIMELINE = [
  { color: '#2563eb', title: 'System processed batch #402', sub: '12 papers analyzed with high confidence',    time: '12 mins ago' },
  { color: '#22c55e', title: 'New report generated',         sub: 'Student ID 104 – Plagiarism check complete',  time: '45 mins ago' },
  { color: '#94a3b8', title: 'Server Maintenance',           sub: 'Node cluster 4 updated to v2.4.1',            time: '2 hours ago' },
  { color: '#f97316', title: 'Integrity Alert',              sub: "High similarity detected in 'Essay_Final.pdf'", time: '4 hours ago' },
  { color: '#2563eb', title: 'Batch #401 Uploaded',          sub: '24 files queued for processing',              time: 'Yesterday'   },
];

const STATUS_MAP = {
  Completed: 'chip-success',
  Processing: 'chip-info',
  Failed: 'chip-error',
};

export default function DashboardPage() {
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      const ok = await checkApiHealth();
      if (ok) {
        console.info('[GRADE] API connected — live data mode');
      } else {
        console.info('[GRADE] API offline — displaying demo data');
      }
    })();
  }, []);

  return (
    <AppShell title="Dashboard" showStatus>
      <div className="page-wrapper">

        {/* ── Stat Cards ── */}
        <section className="grid-3 fade-in-up" style={{ marginBottom: '2rem' }}>
          {STATS.map((s) => (
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
                  <span className="material-symbols-outlined" style={{ fontSize: '0.875rem' }}>timer</span>
                  Estimated: 45 min
                </div>
              )}
            </div>
          ))}
        </section>

        {/* ── Lower Grid ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>

          {/* Recent Uploads Table */}
          <section className="card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '1.5rem', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>Recent Uploads</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--outline)', marginTop: 2 }}>Last 24 hours of submission activity</p>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => navigate('/upload')}>View All</button>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>File Name</th>
                    <th>Student</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {UPLOADS.map((r) => (
                    <tr key={r.file}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          <span className="material-symbols-outlined" style={{ color: 'var(--outline)' }}>description</span>
                          <span style={{ fontWeight: 500 }}>{r.file}</span>
                        </div>
                      </td>
                      <td style={{ color: 'var(--on-surface-variant)' }}>{r.student}</td>
                      <td style={{ color: 'var(--outline)', fontSize: '0.8125rem' }}>{r.date}</td>
                      <td><span className={`chip ${STATUS_MAP[r.status]}`}>{r.status}</span></td>
                      <td style={{ textAlign: 'right', fontWeight: 700, fontSize: '0.875rem' }}>{r.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Activity Timeline */}
          <section className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a', marginBottom: '1.5rem' }}>Activity Timeline</h3>
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', left: '1rem', top: 4, bottom: 4, width: 1, background: '#f1f5f9' }} />
              {TIMELINE.map((t, i) => (
                <div key={i} style={{ position: 'relative', paddingLeft: '2.5rem', marginBottom: '1.25rem' }}>
                  <div style={{ position: 'absolute', left: '0.625rem', top: 4, width: '0.75rem', height: '0.75rem', borderRadius: '50%', background: t.color, border: '2px solid #fff', zIndex: 1 }} />
                  <p style={{ fontSize: '0.875rem', fontWeight: 600, color: '#0f172a' }}>{t.title}</p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--outline)', marginTop: 2 }}>{t.sub}</p>
                  <span style={{ fontSize: '0.625rem', color: 'var(--outline)', display: 'block', marginTop: '0.375rem' }}>{t.time}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* ── CTA Banner ── */}
        <section style={{ marginTop: '2rem', background: 'var(--primary)', borderRadius: 'var(--radius-xl)', padding: '2rem 2.5rem', position: 'relative', overflow: 'hidden', boxShadow: 'var(--shadow-lg)' }}>
          <div style={{ position: 'absolute', top: '-4rem', right: '-4rem', width: '12rem', height: '12rem', background: 'rgba(255,255,255,0.08)', borderRadius: '50%', filter: 'blur(40px)' }} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '2rem', flexWrap: 'wrap', position: 'relative', zIndex: 1 }}>
            <div>
              <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff' }}>Enhance Your Academic Trust</h2>
              <p style={{ color: 'rgba(255,255,255,0.85)', marginTop: '0.5rem', maxWidth: 480, lineHeight: 1.6 }}>AI model v4.2 increases detection accuracy by 15% for complex paraphrasing.</p>
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1.25rem', flexWrap: 'wrap' }}>
                <button className="btn" style={{ background: '#fff', color: 'var(--primary)', fontWeight: 700 }} onClick={() => navigate('/settings')}>View Settings</button>
                <button className="btn" style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.25)', backdropFilter: 'blur(8px)' }}>Upgrade Plan</button>
              </div>
            </div>
            <div style={{ width: '9rem', height: '9rem', background: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(8px)', borderRadius: 'var(--radius-xl)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(255,255,255,0.2)', textAlign: 'center', flexShrink: 0 }}>
              <span className="material-symbols-outlined" style={{ fontSize: '3rem', color: '#fff', fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
              <span style={{ color: '#fff', fontWeight: 700, fontSize: '0.875rem', marginTop: '0.5rem' }}>AI Confidence<br />Engine</span>
              <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.625rem', marginTop: 2 }}>Level 4 Certified</span>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
