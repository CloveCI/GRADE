import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import AppShell from '../components/AppShell';
import { formatExamName } from '../lib/examLabels';
import { getExamDetail, GRADE_SESSION, reportPdfUrl, saveGradeSession } from '../lib/api';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return String(iso);
  }
}

export default function ExamDetailPage() {
  const { examId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const detail = await getExamDetail(examId);
      if (!detail) {
        setError('Exam not found');
      } else {
        setData(detail);
      }
      setLoading(false);
    })();
  }, [examId]);

  const openInEvaluator = (sheet) => {
    saveGradeSession({
      examId: sheet.exam_id || examId,
      sheetId: sheet.id,
      filename: sheet.filename,
      regionsPerPage: undefined, // detected automatically unless the teacher sets a layout
    });
    sessionStorage.removeItem(GRADE_SESSION.resultId);
    navigate('/evaluator');
  };

  return (
    <AppShell title={formatExamName(examId)} showStatus>
      <div className="page-wrapper">
        <p style={{ marginBottom: '1rem' }}>
          <Link to="/processing">← Back to upload</Link>
        </p>

        {loading && <p>Loading…</p>}
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}

        {data && (
          <>
            <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: '0 0 0.5rem' }}>{formatExamName(examId)}</h2>
              <p style={{ fontSize: '0.875rem', color: 'var(--outline)', margin: 0 }}>
                {data.exam?.key_count ?? data.keys?.length ?? 0} questions · {data.sheets?.length ?? 0} sheets · {data.results?.length ?? 0} graded
              </p>
            </div>

            <section style={{ marginBottom: '2rem' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>Marking scheme</h3>
              <div className="card" style={{ padding: '1rem' }}>
                {(data.keys || []).length === 0 ? (
                  <p style={{ color: 'var(--outline)', margin: 0 }}>No keys uploaded yet.</p>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                    {data.keys.map((k) => (
                      <li key={k.id} style={{ marginBottom: '0.35rem' }}>
                        <strong>{k.question_id}</strong> — max {k.max_marks} marks
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>

            <section style={{ marginBottom: '2rem' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>Answer sheets</h3>
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table style={{ width: '100%', fontSize: '0.875rem', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', textAlign: 'left' }}>
                      <th style={{ padding: '0.75rem 1rem' }}>File</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Uploaded</th>
                      <th style={{ padding: '0.75rem 1rem' }} />
                    </tr>
                  </thead>
                  <tbody>
                    {(data.sheets || []).map((s) => (
                      <tr key={s.id} style={{ borderTop: '1px solid #e2e8f0' }}>
                        <td style={{ padding: '0.75rem 1rem' }}>{s.filename}</td>
                        <td style={{ padding: '0.75rem 1rem' }}>{formatDate(s.created_at)}</td>
                        <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                          <button type="button" className="btn btn-secondary btn-sm" onClick={() => openInEvaluator(s)}>
                            Grade in UI
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section>
              <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>Latest results</h3>
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table style={{ width: '100%', fontSize: '0.875rem', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', textAlign: 'left' }}>
                      <th style={{ padding: '0.75rem 1rem' }}>Score</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Graded</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Report</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.results || []).map((r) => (
                      <tr key={r.id} style={{ borderTop: '1px solid #e2e8f0' }}>
                        <td style={{ padding: '0.75rem 1rem' }}>{r.total_marks} / {r.max_total}</td>
                        <td style={{ padding: '0.75rem 1rem' }}>{formatDate(r.created_at)}</td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          <a href={reportPdfUrl(r.id)} target="_blank" rel="noreferrer">PDF</a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}
