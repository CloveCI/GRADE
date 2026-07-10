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
      <div className="page-wrapper" style={{ maxWidth: '1200px', margin: '0 auto', color: '#f1f5f9' }}>
        
        {/* Top metrics row */}
        <section className="grid-3 fade-in-up" style={{ marginBottom: '2rem', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem' }}>
          
          {/* Active Classes */}
          <div className="stat-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: '140px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', letterSpacing: '0.05em' }}>ACTIVE CLASSES</span>
                <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#ffffff', marginTop: '0.25rem' }}>5</div>
              </div>
              <div style={{ marginTop: '0.5rem' }}>
                <svg width="60" height="30" viewBox="0 0 60 30" style={{ overflow: 'visible' }}>
                  <path d="M 0 25 C 10 15, 20 20, 30 10 C 40 5, 50 15, 60 5" fill="none" stroke="#a5b4fc" strokeWidth="2.5" strokeLinecap="round" />
                  <circle cx="60" cy="5" r="3" fill="#6366f1" />
                </svg>
              </div>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span className="material-symbols-outlined" style={{ fontSize: '0.875rem' }}>insights</span>
              <span>Class overview active</span>
            </div>
          </div>

          {/* Students Enrolled */}
          <div className="stat-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: '140px' }}>
            <div>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', letterSpacing: '0.05em' }}>STUDENTS ENROLLED</span>
              <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#ffffff', marginTop: '0.25rem', display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                <span>184</span>
                <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#22c55e', display: 'inline-flex', alignItems: 'center' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '1rem', fontWeight: 'bold' }}>north_east</span>
                </span>
              </div>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#22c55e', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>Trend up and 18</span>
            </div>
          </div>

          {/* Assignments Graded */}
          <div className="stat-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: '140px' }}>
            <div>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', letterSpacing: '0.05em' }}>ASSIGNMENTS GRADED</span>
              <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#ffffff', marginTop: '0.25rem' }}>1,248</div>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>Weekly total</span>
            </div>
          </div>

        </section>

        {/* Charts Section */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
          
          {/* Grading Overview Card */}
          <section className="card" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <div>
                <h3 style={{ fontSize: '1.125rem', fontWeight: 800, color: '#ffffff' }}>Grading Overview</h3>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <select className="form-select" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', borderRadius: '6px', background: 'rgba(255,255,255,0.06)', color: '#ffffff', border: '1px solid rgba(255,255,255,0.1)' }}>
                  <option>Per day</option>
                </select>
                <button type="button" className="btn btn-secondary btn-sm" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#ffffff' }}>More</button>
              </div>
            </div>
            
            {/* SVG Line Area Chart */}
            <div style={{ width: '100%', height: '220px', paddingLeft: '20px' }}>
              <svg width="100%" height="200" viewBox="0 0 500 200" style={{ overflow: 'visible' }}>
                <defs>
                  <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#818cf8" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="#818cf8" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                {/* Grid Lines */}
                <line x1="0" y1="30" x2="500" y2="30" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                <line x1="0" y1="75" x2="500" y2="75" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                <line x1="0" y1="120" x2="500" y2="120" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                <line x1="0" y1="165" x2="500" y2="165" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
                
                {/* Chart Path and Area */}
                <path d="M 0 165 L 80 120 L 160 90 L 240 85 L 320 65 L 400 55 L 480 45 L 500 48 L 500 165 L 0 165 Z" fill="url(#areaGrad)" />
                <path d="M 0 165 L 80 120 L 160 90 L 240 85 L 320 65 L 400 55 L 480 45 L 500 48" fill="none" stroke="#6366f1" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                
                {/* Dots */}
                <circle cx="80" cy="120" r="4" fill="#6366f1" stroke="#ffffff" strokeWidth="2" />
                <circle cx="160" cy="90" r="4" fill="#6366f1" stroke="#ffffff" strokeWidth="2" />
                <circle cx="240" cy="85" r="4" fill="#6366f1" stroke="#ffffff" strokeWidth="2" />
                <circle cx="320" cy="65" r="4" fill="#6366f1" stroke="#ffffff" strokeWidth="2" />
                <circle cx="400" cy="55" r="4" fill="#6366f1" stroke="#ffffff" strokeWidth="2" />
                <circle cx="480" cy="45" r="4" fill="#6366f1" stroke="#ffffff" strokeWidth="2" />
                
                {/* Y-Axis Labels */}
                <text x="-25" y="34" fill="#94a3b8" fontSize="10">100</text>
                <text x="-25" y="79" fill="#94a3b8" fontSize="10">50</text>
                <text x="-25" y="169" fill="#94a3b8" fontSize="10">0</text>
                
                {/* X-Axis Labels */}
                <text x="0" y="190" fill="#94a3b8" fontSize="10">Sun</text>
                <text x="80" y="190" fill="#94a3b8" fontSize="10">Mon</text>
                <text x="160" y="190" fill="#94a3b8" fontSize="10">Tue</text>
                <text x="240" y="190" fill="#94a3b8" fontSize="10">Wed</text>
                <text x="320" y="190" fill="#94a3b8" fontSize="10">Thu</text>
                <text x="400" y="190" fill="#94a3b8" fontSize="10">Fri</text>
                <text x="480" y="190" fill="#94a3b8" fontSize="10">Sat</text>
              </svg>
            </div>
          </section>

          {/* Grade Distribution Card */}
          <section className="card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 800, color: '#ffffff', alignSelf: 'flex-start', marginBottom: '1.5rem' }}>Grade Distribution</h3>
            
            {/* SVG Donut Chart */}
            <div style={{ position: 'relative', width: '120px', height: '120px', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="100%" height="100%" viewBox="0 0 36 36" style={{ transform: 'rotate(-90deg)', overflow: 'visible' }}>
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#6366f1" strokeWidth="3" strokeDasharray="45 55" strokeDashoffset="0" />
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#3b82f6" strokeWidth="3" strokeDasharray="25 75" strokeDashoffset="-45" />
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#ec4899" strokeWidth="3" strokeDasharray="15 85" strokeDashoffset="-70" />
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#f97316" strokeWidth="3" strokeDasharray="10 90" strokeDashoffset="-85" />
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#ef4444" strokeWidth="3" strokeDasharray="5 95" strokeDashoffset="-95" />
              </svg>
            </div>
            
            {/* Donut Legend */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', justifyContent: 'center', width: '100%' }}>
              {[
                { label: 'A', color: '#6366f1' },
                { label: 'B', color: '#3b82f6' },
                { label: 'C', color: '#ec4899' },
                { label: 'D', color: '#f97316' },
                { label: 'F', color: '#ef4444' }
              ].map(item => (
                <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: item.color }} />
                  <span style={{ fontWeight: 600, color: '#94a3b8' }}>{item.label}</span>
                </div>
              ))}
            </div>
          </section>

        </div>

        {/* Bottom row (Recent & Pending) */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
          
          {/* Recent Assignments Table */}
          <section className="card" style={{ padding: '1.5rem', overflow: 'hidden' }}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 800, color: '#ffffff', marginBottom: '1.25rem' }}>Recent Assignments</h3>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '0.75rem 1rem' }}>Assignment</th>
                    <th style={{ textAlign: 'left', padding: '0.75rem 1rem' }}>Status</th>
                    <th style={{ textAlign: 'center', padding: '0.75rem 1rem' }}>AI Score</th>
                    <th style={{ textAlign: 'center', padding: '0.75rem 1rem' }}>Students</th>
                    <th style={{ textAlign: 'right', padding: '0.75rem 1rem' }}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { name: 'Physics 101 - Quiz 3', status: 'Graded', statusColor: '#22c55e', statusBg: 'rgba(34,229,94,0.1)', score: '88%', students: '1 students', date: 'Jan 18, 2023' },
                    { name: 'History - Essay 2', status: 'Pending', statusColor: '#f59e0b', statusBg: 'rgba(245,158,11,0.1)', score: '--', students: '1 students', date: 'Jun 20, 2023' },
                    { name: 'CS204 - Project', status: 'In Review', statusColor: '#3b82f6', statusBg: 'rgba(59,130,246,0.1)', score: '88%', students: '1 students', date: 'Jun 28, 2023' }
                  ].map((row, idx) => (
                    <tr key={idx}>
                      <td style={{ padding: '1rem', fontWeight: 600 }}>{row.name}</td>
                      <td style={{ padding: '1rem' }}>
                        <span style={{
                          display: 'inline-flex', padding: '0.125rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700,
                          background: row.statusBg, color: row.statusColor
                        }}>
                          {row.status}
                        </span>
                      </td>
                      <td style={{ padding: '1rem', textAlign: 'center', fontWeight: 700 }}>{row.score}</td>
                      <td style={{ padding: '1rem', textAlign: 'center', color: '#94a3b8' }}>{row.students}</td>
                      <td style={{ padding: '1rem', textAlign: 'right', color: '#94a3b8', fontSize: '0.8125rem' }}>{row.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Pending Tasks */}
          <section className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 800, color: '#ffffff', marginBottom: '1.25rem' }}>Pending Tasks</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {[
                { task: 'Grade English Lit Essays', time: '2 minutes ago' },
                { task: 'Finalize Math Midterm Scores', time: '2 minutes ago' },
                { task: 'Review CS Submissions', time: '2 minutes ago' }
              ].map((task, idx) => (
                <div key={idx} style={{
                  padding: '1rem',
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: '12px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.25rem'
                }}>
                  <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#ffffff' }}>{task.task}</div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{task.time}</div>
                </div>
              ))}
            </div>
          </section>

        </div>

      </div>
    </AppShell>
  );
}
