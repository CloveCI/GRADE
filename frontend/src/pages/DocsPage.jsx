import { Link } from 'react-router-dom';
import AppShell from '../components/AppShell';

const HELP_SECTIONS = [
  {
    title: 'Getting started',
    items: [
      { to: '/processing', label: 'Grade new papers', desc: 'Upload the marking scheme and a student answer sheet.' },
      { to: '/evaluator', label: 'Review scores', desc: 'See marks and feedback for each question.' },
      { to: '/reports', label: 'Download reports', desc: 'Save a PDF summary of any completed grading.' },
    ],
  },
  {
    title: 'Tips',
    bullets: [
      'Use a clear scan or PDF of the handwritten answer sheet.',
      'Upload the official marking scheme as a Word (.docx) file when possible.',
      'Pick the correct subject from the list so scores match the right exam.',
    ],
  },
];

export default function DocsPage() {
  return (
    <AppShell title="Help">
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800, marginBottom: '0.5rem' }}>How to use GRADE</h1>
        <p style={{ color: 'var(--on-surface-variant)', marginBottom: '2.5rem', lineHeight: 1.6 }}>
          GRADE reads handwritten exam papers, compares answers to your marking scheme, and produces scores you can review and export.
        </p>

        {HELP_SECTIONS.map((section) => (
          <section key={section.title} style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>{section.title}</h2>
            {section.items && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {section.items.map(({ to, label, desc }) => (
                  <Link
                    key={to}
                    to={to}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.25rem',
                      borderRadius: 12, border: '1px solid #e2e8f0', textDecoration: 'none', color: 'inherit',
                    }}
                  >
                    <span className="material-symbols-outlined" style={{ color: 'var(--primary)' }}>arrow_forward</span>
                    <div>
                      <div style={{ fontWeight: 600 }}>{label}</div>
                      <div style={{ fontSize: '0.875rem', color: 'var(--on-surface-variant)' }}>{desc}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
            {section.bullets && (
              <ul style={{ paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--on-surface-variant)' }}>
                {section.bullets.map((b) => <li key={b}>{b}</li>)}
              </ul>
            )}
          </section>
        ))}

        <Link to="/dashboard" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem', color: 'var(--primary)', fontWeight: 600 }}>
          <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>arrow_back</span>
          Back to dashboard
        </Link>
      </div>
    </AppShell>
  );
}
