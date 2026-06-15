import { useState, useEffect } from 'react';
import AppShell from '../components/AppShell';
import { apiFetch, checkApiHealth } from '../lib/api';

const OCR_CARDS = [
  { id: 'google', name: 'Google Cloud Vision', desc: 'Optimized for handwritten text and low-res scans.',      icon: { text: 'G',   bg: '#e8f0fe', color: '#4285f4' } },
  { id: 'azure',  name: 'Azure Form Recognizer', desc: 'Superior table extraction and layout analysis.',       icon: { text: 'Az',  bg: '#e8f4fd', color: '#0078d4' } },
  { id: 'paddle', name: 'PaddleOCR',             desc: 'Open-source multi-lingual with strong accuracy.',      icon: { text: 'PAD', bg: '#fef9ec', color: '#f2a519', small: true } },
  { id: 'trocr',  name: 'TrOCR',                 desc: 'Microsoft transformer-based handwriting model.',       icon: { text: 'TR',  bg: '#f5f3ff', color: '#7c3aed', small: true } },
];

export default function SettingsPage() {
  const [selectedOCR, setSelectedOCR] = useState('google');
  const [llmEnabled, setLlmEnabled] = useState(true);
  const [hitl, setHitl] = useState(false);
  const [cloudOnly, setCloudOnly] = useState(false);
  const [googleOnly, setGoogleOnly] = useState(false);
  const [keyVisibility, setKeyVisibility] = useState({ google: false, gemini: false, azure: false });
  const [dbStatus, setDbStatus] = useState('connected'); // 'connected' | 'testing' | 'unreachable'
  const [theme, setTheme] = useState(() => localStorage.getItem('grade-theme') || 'light');
  const [saveState, setSaveState] = useState('idle'); // 'idle' | 'saving' | 'saved'

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('grade-theme', theme);
  }, [theme]);

  const toggleKey = (key) => setKeyVisibility(prev => ({ ...prev, [key]: !prev[key] }));

  const testConnection = async () => {
    setDbStatus('testing');
    const ok = await checkApiHealth();
    setDbStatus(ok ? 'connected' : 'unreachable');
  };

  const saveConfig = async () => {
    setSaveState('saving');
    const payload = { ocr_provider: selectedOCR, llm_enabled: llmEnabled, human_in_loop: hitl, cloud_only: cloudOnly, google_only: googleOnly };
    await apiFetch('/config', { method: 'POST', body: JSON.stringify(payload) });
    localStorage.setItem('grade-config', JSON.stringify(payload));
    setSaveState('saved');
    setTimeout(() => setSaveState('idle'), 2000);
  };

  const DB_STATUS_MAP = {
    connected:   { dot: '#22c55e', label: 'Connected',   labelColor: '#15803d', bg: '#f0fdf4' },
    testing:     { dot: '#f59e0b', label: 'Testing…',    labelColor: '#d97706', bg: '#fffbeb' },
    unreachable: { dot: '#ef4444', label: 'Unreachable', labelColor: '#b91c1c', bg: '#fef2f2' },
  };
  const dbInfo = DB_STATUS_MAP[dbStatus];

  return (
    <AppShell title="System Configuration" showStatus={false}>
      <div className="page-wrapper" style={{ maxWidth: 880 }}>

        {/* Page header */}
        <header style={{ marginBottom: '3rem' }} className="fade-in-up">
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '0.375rem' }}>System Configuration</h2>
          <p style={{ color: 'var(--on-surface-variant)', maxWidth: 520 }}>
            Manage your academic integrity engine, API connections, and interface preferences. Changes are applied globally to the institution.
          </p>
        </header>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

          {/* ── OCR Engine ── */}
          <section className="settings-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.75rem' }}>
              <div>
                <h3>OCR Engine</h3>
                <p style={{ marginBottom: 0 }}>Select the optical character recognition provider for document digitization.</p>
              </div>
              <span className="chip chip-info">High Precision</span>
            </div>
            <div className="ocr-grid">
              {OCR_CARDS.map(card => (
                <label
                  key={card.id}
                  className={`ocr-card${selectedOCR === card.id ? ' selected' : ''}`}
                  onClick={() => setSelectedOCR(card.id)}
                >
                  <input type="radio" name="ocr" value={card.id} checked={selectedOCR === card.id} onChange={() => setSelectedOCR(card.id)} />
                  <div className="ocr-card-top">
                    <div className="ocr-icon" style={{ background: card.icon.bg, color: card.icon.color, fontWeight: 800, fontSize: card.icon.small ? '0.625rem' : '0.75rem' }}>
                      {card.icon.text}
                    </div>
                    <div className="check-indicator">
                      {selectedOCR === card.id && (
                        <span className="material-symbols-outlined" style={{ fontSize: '0.875rem', color: '#fff', fontVariationSettings: "'FILL' 1" }}>check</span>
                      )}
                    </div>
                  </div>
                  <div className="ocr-card-name">{card.name}</div>
                  <div className="ocr-card-desc">{card.desc}</div>
                </label>
              ))}
            </div>

            {/* Cloud-only toggles */}
            <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {[
                { id: 'cloudOnly', state: cloudOnly, setState: setCloudOnly, label: 'Cloud-only mode', desc: 'Disable local PaddleOCR/TrOCR fallback' },
                { id: 'googleOnly', state: googleOnly, setState: setGoogleOnly, label: 'Google-only mode', desc: 'Cloud tier uses only Google Vision (no Azure fallback)' },
              ].map(tog => (
                <div key={tog.id} className="toggle-row">
                  <div>
                    <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{tog.label}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>{tog.desc}</div>
                  </div>
                  <label className="toggle">
                    <input type="checkbox" checked={tog.state} onChange={e => tog.setState(e.target.checked)} />
                    <div className="toggle-track" />
                    <div className="toggle-thumb" />
                  </label>
                </div>
              ))}
            </div>
          </section>

          {/* ── AI Grading ── */}
          <section className="settings-section">
            <h3 style={{ marginBottom: '1.5rem' }}>AI Grading &amp; Intelligence</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div className="toggle-row featured">
                <div style={{ display: 'flex', gap: '0.875rem', alignItems: 'flex-start' }}>
                  <span className="material-symbols-outlined" style={{ color: 'var(--primary)', marginTop: 2, fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                  <div>
                    <p style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0f172a' }}>Enable LLM-based Scoring</p>
                    <p style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>Use Gemini for nuanced semantic analysis and rubric-based grading (requires <code>GRADE_ENABLE_LLM</code>).</p>
                  </div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={llmEnabled} onChange={e => setLlmEnabled(e.target.checked)} />
                  <div className="toggle-track" />
                  <div className="toggle-thumb" />
                </label>
              </div>

              <div className="toggle-row">
                <div style={{ display: 'flex', gap: '0.875rem', alignItems: 'flex-start' }}>
                  <span className="material-symbols-outlined" style={{ color: 'var(--on-surface-variant)', marginTop: 2 }}>person_search</span>
                  <div>
                    <p style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0f172a' }}>Human-in-the-loop Validation</p>
                    <p style={{ fontSize: '0.75rem', color: 'var(--outline)' }}>Require manual review for scores with confidence levels below 85%.</p>
                  </div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={hitl} onChange={e => setHitl(e.target.checked)} />
                  <div className="toggle-track" />
                  <div className="toggle-thumb" />
                </label>
              </div>
            </div>
          </section>

          {/* ── API + DB Row ── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>

            {/* API Keys */}
            <section className="settings-section" style={{ display: 'flex', flexDirection: 'column' }}>
              <h3>API Configuration</h3>
              <p>Credentials for OCR and LLM services.</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
                {[
                  { id: 'google', label: 'Google Cloud API Key', placeholder: 'AIzaSy…' },
                  { id: 'gemini', label: 'Gemini API Key',        placeholder: 'Enter key…' },
                  { id: 'azure',  label: 'Azure Cognitive Services Key', placeholder: 'Enter key…' },
                ].map(k => (
                  <div key={k.id} className="form-group">
                    <label className="form-label" htmlFor={`${k.id}-key`}>{k.label}</label>
                    <div style={{ position: 'relative' }}>
                      <input
                        className="form-input"
                        type={keyVisibility[k.id] ? 'text' : 'password'}
                        id={`${k.id}-key`}
                        placeholder={k.placeholder}
                        autoComplete="off"
                      />
                      <button
                        className="icon-btn"
                        style={{ position: 'absolute', right: '0.25rem', top: '50%', transform: 'translateY(-50%)' }}
                        onClick={() => toggleKey(k.id)}
                        title="Show/hide key"
                        type="button"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>
                          {keyVisibility[k.id] ? 'visibility_off' : 'visibility'}
                        </span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid #f1f5f9' }}>
                <button className="btn-ghost btn btn-sm" style={{ fontSize: '0.8125rem' }}>Rotate Keys &amp; Logout Others</button>
              </div>
            </section>

            {/* DB + Theme */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

              {/* Database Status */}
              <section className="settings-section">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
                  <h3>Database</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: dbInfo.bg, padding: '0.25rem 0.75rem', borderRadius: 'var(--radius-full)' }}>
                    <span style={{ width: '0.5rem', height: '0.5rem', background: dbInfo.dot, borderRadius: '50%', display: 'block', ...(dbStatus === 'testing' ? { animation: 'pulse-dot 1s infinite' } : {}) }} />
                    <span style={{ fontSize: '0.625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: dbInfo.labelColor }}>{dbInfo.label}</span>
                  </div>
                </div>
                <div className="form-group" style={{ marginBottom: '0.875rem' }}>
                  <label className="form-label">Connection String (GRADE_DATABASE_URL)</label>
                  <code className="code-block">postgresql://grade:grade@127.0.0.1:5433/grade_test</code>
                </div>
                <button className="btn btn-secondary" style={{ width: '100%', marginTop: '0.25rem' }} onClick={testConnection}>
                  Test Connection
                </button>
              </section>

              {/* Theme */}
              <section className="settings-section">
                <h3 style={{ marginBottom: '1.25rem' }}>Theme</h3>
                <div className="theme-toggle" role="radiogroup" aria-label="Theme selection">
                  <button className={`theme-btn${theme === 'light' ? ' active' : ''}`} onClick={() => setTheme('light')}>
                    <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>light_mode</span>
                    Light
                  </button>
                  <button className={`theme-btn${theme === 'dark' ? ' active' : ''}`} onClick={() => setTheme('dark')}>
                    <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>dark_mode</span>
                    Dark
                  </button>
                </div>
              </section>
            </div>
          </div>

          {/* ── Action Footer ── */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', paddingTop: '1.5rem', borderTop: '1px solid #f1f5f9' }}>
            <button className="btn btn-secondary" onClick={() => window.location.reload()}>Discard Changes</button>
            <button
              className="btn btn-primary btn-lg"
              id="save-btn"
              onClick={saveConfig}
              disabled={saveState !== 'idle'}
              style={saveState === 'saved' ? { background: '#22c55e' } : {}}
            >
              <span className="material-symbols-outlined">{saveState === 'saved' ? 'check_circle' : saveState === 'saving' ? 'hourglass_top' : 'save'}</span>
              {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved!' : 'Save Configuration'}
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
