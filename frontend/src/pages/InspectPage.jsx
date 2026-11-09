import { useState, useEffect } from 'react';
import AppShell from '../components/AppShell';
import {
  searchRag,
  getExams,
  getSheetChunks,
  getExamKeyChunks,
} from '../lib/api';
import { formatExamName } from '../lib/examLabels';

export default function InspectPage() {
  const [query, setQuery] = useState('');
  const [examId, setExamId] = useState('');
  const [sheetId, setSheetId] = useState('');
  const [corpus, setCorpus] = useState('both');
  const [results, setResults] = useState([]);
  const [chunks, setChunks] = useState([]);
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      const list = await getExams();
      if (Array.isArray(list)) setExams(list);
    })();
  }, []);

  const runSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    try {
      const hits = await searchRag(query, { examId: examId || undefined, sheetId: sheetId || undefined, topK: 8 });
      setResults(Array.isArray(hits) ? hits : []);
    } catch (err) {
      setError(err.message);
      setResults([]);
    }
    setLoading(false);
  };

  const loadChunks = async () => {
    setLoading(true);
    setError('');
    try {
      if (corpus === 'keys' && examId) {
        setChunks(await getExamKeyChunks(examId) || []);
      } else if (corpus === 'sheet' && sheetId) {
        setChunks(await getSheetChunks(sheetId) || []);
      } else {
        const keyChunks = examId ? (await getExamKeyChunks(examId) || []) : [];
        const sheetChunks = sheetId ? (await getSheetChunks(sheetId) || []) : [];
        setChunks([...keyChunks.map((c) => ({ ...c, corpus: 'key' })), ...sheetChunks.map((c) => ({ ...c, corpus: 'sheet' }))]);
      }
    } catch (err) {
      setError(err.message);
      setChunks([]);
    }
    setLoading(false);
  };

  return (
    <AppShell title="RAG inspector" showStatus>
      <div className="page-wrapper" style={{ maxWidth: 900 }}>
        <p style={{ color: 'var(--outline)', marginBottom: '1.5rem' }}>
          Debug retrieval quality — search the vector index or browse stored chunks.
        </p>

        <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Hybrid search</h3>
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            <input className="form-input" placeholder="Paste student answer text…" value={query}
              onChange={(e) => setQuery(e.target.value)} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <select className="form-select" value={examId} onChange={(e) => setExamId(e.target.value)}>
                <option value="">Any exam</option>
                {exams.map((e) => <option key={e.id} value={e.id}>{formatExamName(e.id)}</option>)}
              </select>
              <input className="form-input" placeholder="Sheet ID (optional)" value={sheetId}
                onChange={(e) => setSheetId(e.target.value)} />
            </div>
            <button type="button" className="btn btn-primary btn-sm" onClick={runSearch} disabled={loading}>Search</button>
          </div>
          {results.length > 0 && (
            <ul style={{ marginTop: '1rem', padding: 0, listStyle: 'none' }}>
              {results.map((r, i) => (
                <li key={r.chunk_id || i} className="card" style={{ padding: '0.75rem', marginBottom: '0.5rem', fontSize: '0.8125rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <span className="chip chip-neutral">score {typeof r.score === 'number' ? r.score.toFixed(3) : r.score}</span>
                    <span style={{ color: 'var(--outline)' }}>p{r.page} · {r.region || '—'}</span>
                  </div>
                  <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{r.text}</p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card" style={{ padding: '1.25rem' }}>
          <h3 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Chunk browser</h3>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
            {['keys', 'sheet', 'both'].map((c) => (
              <button key={c} type="button" className={`btn btn-sm ${corpus === c ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setCorpus(c)}>{c}</button>
            ))}
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={loadChunks} disabled={loading}>Load chunks</button>
          {chunks.length > 0 && (
            <ul style={{ marginTop: '1rem', padding: 0, listStyle: 'none', maxHeight: 400, overflow: 'auto' }}>
              {chunks.map((c, i) => (
                <li key={c.chunk_id || i} style={{ padding: '0.5rem 0', borderBottom: '1px solid #e2e8f0', fontSize: '0.8125rem' }}>
                  <strong>{c.question_id || c.region || c.chunk_index}</strong>
                  <p style={{ margin: '0.25rem 0 0', color: 'var(--outline)' }}>{(c.text || c.text_content || '').slice(0, 200)}…</p>
                </li>
              ))}
            </ul>
          )}
        </div>

        {error && <p style={{ color: '#b91c1c', marginTop: '1rem' }}>{error}</p>}
      </div>
    </AppShell>
  );
}
