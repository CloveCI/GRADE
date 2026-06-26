import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Footer from '../components/Footer';
import { getExams } from '../lib/api';

export default function LandingPage() {
  const navigate = useNavigate();

  useEffect(() => {
    getExams().then((data) => {
      if (Array.isArray(data) && data.length) {
        console.info('[GRADE] Exams from API:', data.length);
      }
    });
  }, []);

  useEffect(() => {
    const handler = (e) => {
      const link = e.target.closest('a[data-scroll]');
      if (!link) return;
      e.preventDefault();
      const target = document.querySelector(link.getAttribute('href'));
      if (target) target.scrollIntoView({ behavior: 'smooth' });
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  return (
    <>
      {/* ── Public Navigation ── */}
      <nav className="pub-nav" role="navigation">
        <div className="pub-nav-inner">
          <Link to="/" className="pub-nav-logo" style={{ textDecoration: 'none', color: 'inherit' }}>GRADE</Link>
          <div className="pub-nav-links">
            <a href="#features" data-scroll className="active">Features</a>
            <a href="#pipeline" data-scroll>How It Works</a>
            <Link to="/dashboard">Dashboard</Link>
            <Link to="/docs">Docs</Link>
          </div>
          <div className="pub-nav-actions">
            <button type="button" className="nav-login" onClick={() => navigate('/dashboard')}>Login</button>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate('/processing')}>Get Started</button>
          </div>
        </div>
      </nav>

      <main>
        {/* ── Hero Section ── */}
        <section className="bg-dots" style={{ backgroundColor: 'var(--surface)' }}>
          <div className="landing-hero">
            {/* Left: Text */}
            <div className="fade-in-up">
              <div className="hero-badge">
                <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                <span>AI-Powered Evaluation</span>
              </div>
              <h1 style={{ fontSize: 'clamp(2.25rem,4.5vw,3.75rem)', fontWeight: 800, lineHeight: 1.1, letterSpacing: '-0.03em', marginBottom: '1.5rem' }}>
                Automated Handwritten Answer Evaluation&nbsp;using&nbsp;AI
              </h1>
              <p style={{ fontSize: '1.125rem', color: 'var(--on-surface-variant)', maxWidth: 500, lineHeight: 1.7, marginBottom: '2.5rem' }}>
                Harnessing advanced OCR and LLM-based scoring to grade handwritten exam papers with clinical precision and zero manual bias.
              </p>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <button className="btn btn-primary btn-lg" onClick={() => navigate('/processing')}>
                  <span className="material-symbols-outlined">upload_file</span>
                  Upload Answer Sheet
                </button>
                <button className="btn btn-secondary btn-lg" onClick={() => navigate('/evaluator')}>
                  <span className="material-symbols-outlined">play_circle</span>
                  View Demo
                </button>
              </div>
            </div>

            {/* Right: Visual */}
            <div className="hero-visual">
              <div className="hero-glow-1" />
              <div className="hero-img-wrap">
                <img
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuA5qBuGOpUYMUT0r4QsO_UzEn1sRtW8JWIB62m__H-dXrPN4Re_FPAaNDEsnEyRCtQMMgDhKsPVvxmteSglwNjunCV2w4cD08Nkj0J5QGIxBa7Dmb7oW_Ce7P-YUncf2r0q3VLxuE1BWhsKg4Kgwpuu2inuLMVqyYxuwej7HuASTl3IamlefaiZ-Q_hwjOMRw2BpVakgIqcMYi4Qrq1EaVJ34QdnOdYTV3yGjV-XMzQUdrAr0gygXsl2f2yjj6nG2_03-pNNgDRM_8"
                  alt="Handwritten exam paper being scanned with AI interface"
                />
                <div className="hero-stat-bubble">
                  <div className="icon-circle">
                    <span className="material-symbols-outlined">fact_check</span>
                  </div>
                  <div>
                    <div className="label">Accuracy Rate</div>
                    <div className="val">99.8%</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Pipeline Section ── */}
        <section className="section" id="pipeline" style={{ background: 'var(--surface-container-lowest)' }}>
          <div className="section-inner">
            <div className="section-header">
              <h2>Precision Engineering Pipeline</h2>
              <p>The seamless journey from ink on paper to structured, verified insights.</p>
            </div>
            <div className="pipeline-flow" style={{ gap: 0 }}>
              {[
                { icon: 'document_scanner', label: 'Scan', sub: 'Capture high-res imagery' },
                { icon: 'grid_view', label: 'OpenCV Segmentation', sub: 'Isolating regions of interest' },
                { icon: 'text_fields', label: 'OCR Engine', sub: 'Multi-model text extraction' },
                { icon: 'psychology', label: 'AI Scoring', sub: 'Contextual semantic evaluation', featured: true },
                { icon: 'picture_as_pdf', label: 'PDF Report', sub: 'Verified academic transcript' },
              ].map((node, i, arr) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
                  <div className="pipeline-node">
                    <div className={`pipeline-node-icon${node.featured ? ' featured' : ''}`}>
                      <span className="material-symbols-outlined" style={node.featured ? { fontVariationSettings: "'FILL' 1" } : {}}>{node.icon}</span>
                    </div>
                    <div className="pipeline-node-label">{node.label}</div>
                    <div className="pipeline-node-sub">{node.sub}</div>
                  </div>
                  {i < arr.length - 1 && <div className="pipeline-connector" />}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Feature Highlights ── */}
        <section className="section" id="features" style={{ background: 'var(--surface)' }}>
          <div className="section-inner">
            <div className="bento-grid">
              {/* Multi-OCR (2 cols) */}
              <div className="feature-card bento-col-2">
                <div>
                  <div className="feature-icon">
                    <span className="material-symbols-outlined">translate</span>
                  </div>
                  <h3>Multi-OCR Support</h3>
                  <p>Leveraging multiple OCR backends simultaneously — Google Cloud Vision, Azure, PaddleOCR, and TrOCR — to decode handwriting in any style with extreme fidelity.</p>
                  <div className="feature-tags">
                    {['Google Cloud Vision', 'Azure Form Recognizer', 'PaddleOCR', 'TrOCR'].map(tag => (
                      <span key={tag} className="feature-tag">{tag}</span>
                    ))}
                  </div>
                </div>
                <div style={{ position: 'absolute', bottom: '1.5rem', right: '1.5rem', opacity: 0.05 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '7rem' }}>language</span>
                </div>
              </div>

              {/* Rubric-based (1 col) */}
              <div className="feature-card">
                <div>
                  <div className="feature-icon">
                    <span className="material-symbols-outlined">rule</span>
                  </div>
                  <h3>Rubric-Based Grading</h3>
                  <p>Upload your evaluation criteria. The LLM cross-references every answer against your specific marking scheme.</p>
                </div>
                <div className="score-bars">
                  {[['Content Accuracy', '82%'], ['Methodology', '67%'], ['Presentation', '100%']].map(([label, w]) => (
                    <div key={label} className="score-bar-row">
                      <span className="score-bar-label">{label}</span>
                      <div className="score-bar-track"><div className="score-bar-fill" style={{ width: w }} /></div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Instant Analytics (3 cols) */}
              <div className="feature-card bento-col-3">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', alignItems: 'flex-start', flex: 1 }}>
                  <div>
                    <div className="feature-icon">
                      <span className="material-symbols-outlined">monitoring</span>
                    </div>
                    <h3>Instant Analytics</h3>
                    <p>Gain immediate insights into class performance, common misconceptions, and item difficulty indices right after the scan is complete.</p>
                    <Link
                      to="/reports"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem', color: 'var(--primary)', fontWeight: 600, fontSize: '0.875rem', marginTop: '1rem' }}
                    >
                      Explore Reports Dashboard
                      <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>arrow_forward</span>
                    </Link>
                  </div>
                </div>
                <div className="stat-grid" style={{ marginTop: 0, alignSelf: 'flex-end' }}>
                  {[['12.4s', 'Avg. Grading Time'], ['0%', 'Manual Bias'], ['850k', 'Papers Processed'], ['42', 'Languages Supported']].map(([big, lbl]) => (
                    <div key={lbl} className="stat-tile">
                      <div className="big">{big}</div>
                      <div className="lbl">{lbl}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── CTA Section ── */}
        <section className="cta-section">
          <div className="cta-box">
            <h2>Ready to transform your evaluation process?</h2>
            <p>Join leading universities and examination boards using GRADE to ensure fair, fast, and accurate scoring.</p>
            <div className="cta-actions">
              <button className="btn-white" onClick={() => navigate('/processing')}>Get Started Free</button>
              <button className="btn-outline-white">Contact Sales</button>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}
