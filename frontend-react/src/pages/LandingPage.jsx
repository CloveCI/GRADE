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

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('active');
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    const animElements = document.querySelectorAll('.reveal');
    animElements.forEach((el) => observer.observe(el));

    return () => {
      animElements.forEach((el) => observer.unobserve(el));
    };
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

      <main style={{
        background: 'linear-gradient(to bottom, #090e1f 0%, #151b38 35%, #2a2559 60%, #e0dbfa 85%, #ffffff 100%)',
        minHeight: '100vh'
      }}>
        {/* ── Hero Section ── */}
        <section className="landing-hero-section" style={{
          position: 'relative',
          background: 'transparent',
          padding: '8rem 2rem 6rem',
          color: '#ffffff',
          overflow: 'hidden'
        }}>
          {/* Glowing element backgrounds */}
          <div style={{ position: 'absolute', left: '15%', top: '35%', width: '500px', height: '500px', transform: 'translate(-50%, -50%)', background: 'radial-gradient(circle, rgba(168, 85, 247, 0.28) 0%, rgba(99, 102, 241, 0.12) 50%, rgba(0,0,0,0) 70%)', filter: 'blur(80px)', pointerEvents: 'none', zIndex: 1 }} />
          <div style={{ position: 'absolute', right: '15%', top: '45%', width: '600px', height: '600px', transform: 'translate(30%, -50%)', background: 'radial-gradient(circle, rgba(99, 102, 241, 0.35) 0%, rgba(168, 85, 247, 0.15) 50%, rgba(0,0,0,0) 70%)', filter: 'blur(90px)', pointerEvents: 'none', zIndex: 1 }} />

          <div className="landing-hero" style={{ position: 'relative', zIndex: 2, display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '4rem', alignItems: 'center', maxWidth: '1200px', margin: '0 auto' }}>
            {/* Left: Text */}
            <div className="fade-in-up" style={{ textAlign: 'left' }}>
              <div className="hero-badge">
                <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1", fontSize: '0.875rem' }}>auto_awesome</span>
                <span>AI-Powered Evaluation</span>
              </div>
              <h1 style={{ fontSize: 'clamp(2.5rem, 5vw, 3.8rem)', fontWeight: 800, lineHeight: 1.1, letterSpacing: '-0.03em', marginBottom: '1.5rem', color: '#ffffff' }}>
                Automated Handwritten Answer Evaluation using AI
              </h1>
              <p style={{ fontSize: '1.125rem', color: 'rgba(255, 255, 255, 0.7)', maxWidth: 520, lineHeight: 1.7, marginBottom: '2.5rem' }}>
                AI-powered handwritten exam grading platform automatically runs like the northern lights.
              </p>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <button className="btn btn-grad btn-lg" onClick={() => navigate('/processing')} style={{ borderRadius: '9999px', padding: '0.75rem 2rem' }}>
                  <span className="material-symbols-outlined">upload_file</span>
                  Upload Answer Sheet
                </button>
                <button className="btn btn-outline-glass btn-lg" onClick={() => navigate('/evaluator')} style={{ borderRadius: '9999px', padding: '0.75rem 2rem' }}>
                  <span className="material-symbols-outlined">play_circle</span>
                  View Demo
                </button>
              </div>
            </div>

            {/* Right: Visual */}
            <div className="hero-visual">
              <div className="hero-glow-1" />
              
              <div style={{ position: 'relative', width: '380px', height: '420px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {/* Background stacked page 1 */}
                <div style={{
                  position: 'absolute',
                  background: 'rgba(255,255,255,0.06)',
                  backdropFilter: 'blur(8px)',
                  borderRadius: '16px',
                  width: '280px',
                  height: '350px',
                  transform: 'rotate(-8deg) translate(-25px, 15px)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  zIndex: 1
                }} />

                {/* Background stacked page 2 */}
                <div style={{
                  position: 'absolute',
                  background: 'rgba(255,255,255,0.12)',
                  backdropFilter: 'blur(8px)',
                  borderRadius: '16px',
                  width: '280px',
                  height: '350px',
                  transform: 'rotate(5deg) translate(20px, -20px)',
                  border: '1px solid rgba(255,255,255,0.12)',
                  zIndex: 2
                }} />

                {/* Main active page */}
                <div className="floating-element" style={{
                  position: 'relative',
                  background: '#ffffff',
                  borderRadius: '16px',
                  padding: '24px',
                  boxShadow: '0 20px 40px rgba(0,0,0,0.25)',
                  width: '280px',
                  border: '1px solid rgba(255,255,255,0.9)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  color: '#1e293b',
                  zIndex: 3,
                  transform: 'rotate(-2deg)'
                }}>
                  {/* Decorative lines at the top */}
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                    <div style={{ width: '40px', height: '4px', background: '#e2e8f0', borderRadius: '2px' }} />
                    <div style={{ width: '80px', height: '4px', background: '#e2e8f0', borderRadius: '2px' }} />
                  </div>

                  {/* Answer Region 1 */}
                  <div style={{ border: '1px dashed #c084fc', borderRadius: '8px', padding: '10px', background: '#faf5ff', textAlign: 'left' }}>
                    <div style={{ fontSize: '9px', fontWeight: 800, color: '#a855f7', marginBottom: '4px' }}>1</div>
                    <div style={{ fontFamily: 'monospace', fontSize: '11px', fontWeight: 600, color: '#3b0764' }}>∫(3x²+2x)dx = x³+x²+C</div>
                    <div style={{ fontSize: '10px', fontWeight: 700, color: '#22c55e', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '2px' }}>
                      <span style={{ fontSize: '11px', marginRight: '2px' }}>✔</span> Full Marks
                    </div>
                  </div>

                  {/* Answer Region 2 */}
                  <div style={{ border: '1px dashed #c084fc', borderRadius: '8px', padding: '10px', background: '#faf5ff', textAlign: 'left' }}>
                    <div style={{ fontSize: '9px', fontWeight: 800, color: '#a855f7', marginBottom: '4px' }}>2</div>
                    <div style={{ fontFamily: 'monospace', fontSize: '11px', fontWeight: 600, color: '#3b0764' }}>F = ma (Newton's 2nd Law)</div>
                    <div style={{ fontSize: '10px', fontWeight: 700, color: '#22c55e', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '2px' }}>
                      <span style={{ fontSize: '11px', marginRight: '2px' }}>✔</span> Full Marks
                    </div>
                  </div>

                  {/* Answer Region 3 */}
                  <div style={{ border: '1px dashed #c084fc', borderRadius: '8px', padding: '10px', background: '#faf5ff', textAlign: 'left' }}>
                    <div style={{ fontSize: '9px', fontWeight: 800, color: '#a855f7', marginBottom: '4px' }}>3</div>
                    <div style={{ fontFamily: 'monospace', fontSize: '11px', fontWeight: 600, color: '#3b0764' }}>E = mc² (mass-energy equiv.)</div>
                    <div style={{ fontSize: '10px', fontWeight: 700, color: '#f97316', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '2px' }}>
                      <span style={{ fontSize: '12px', marginRight: '2px', lineHeight: '1' }}>~</span> Partial Credit
                    </div>
                  </div>
                </div>

                {/* Floating stat 1: Accuracy (Top Left) */}
                <div className="floating-element" style={{
                  position: 'absolute',
                  top: '10px',
                  left: '-35px',
                  background: 'rgba(255, 255, 255, 0.85)',
                  backdropFilter: 'blur(12px)',
                  border: '1px solid rgba(255, 255, 255, 0.4)',
                  padding: '12px 16px',
                  borderRadius: '16px',
                  boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  zIndex: 10
                }}>
                  <span style={{ fontSize: '8px', fontWeight: 800, color: '#64748b', letterSpacing: '0.05em' }}>ACCURACY</span>
                  <span style={{ fontSize: '20px', fontWeight: 800, color: '#0f172a' }}>99.8%</span>
                  <svg width="24" height="24" viewBox="0 0 36 36" style={{ marginTop: '2px' }}>
                    <circle cx="18" cy="18" r="16" fill="none" stroke="#e2e8f0" strokeWidth="3" />
                    <circle cx="18" cy="18" r="16" fill="none" stroke="#6366f1" strokeWidth="3" strokeDasharray="100" strokeDashoffset="0.2" strokeLinecap="round" />
                  </svg>
                </div>

                {/* Floating stat 2: Avg Time (Top Right) */}
                <div className="floating-element" style={{
                  position: 'absolute',
                  top: '40px',
                  right: '-45px',
                  background: 'rgba(255, 255, 255, 0.85)',
                  backdropFilter: 'blur(12px)',
                  border: '1px solid rgba(255, 255, 255, 0.4)',
                  padding: '14px 20px',
                  borderRadius: '16px',
                  boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  zIndex: 10
                }}>
                  <span style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', lineHeight: '1' }}>12.4s</span>
                  <span style={{ fontSize: '8px', fontWeight: 800, color: '#64748b', letterSpacing: '0.05em', marginTop: '4px' }}>AVG TIME</span>
                </div>

                {/* Floating stat 3: Papers (Bottom Right) */}
                <div className="floating-element" style={{
                  position: 'absolute',
                  bottom: '30px',
                  right: '-35px',
                  background: 'rgba(255, 255, 255, 0.85)',
                  backdropFilter: 'blur(12px)',
                  border: '1px solid rgba(255, 255, 255, 0.4)',
                  padding: '14px 20px',
                  borderRadius: '16px',
                  boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  zIndex: 10
                }}>
                  <span style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', lineHeight: '1' }}>850k</span>
                  <span style={{ fontSize: '8px', fontWeight: 800, color: '#64748b', letterSpacing: '0.05em', marginTop: '4px' }}>PAPERS</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Pipeline Section ── */}
        <section className="section pipeline-section" id="pipeline" style={{ background: 'transparent', padding: '5rem 2rem 5rem' }}>
          <div className="section-inner" style={{ maxWidth: '1200px', margin: '0 auto', textAlign: 'center' }}>
            <div className="section-header reveal" style={{ marginBottom: '4rem' }}>
              <h2 style={{ fontSize: '2.25rem', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em' }}>Precision Engineering Pipeline</h2>
              <p style={{ fontSize: '1.05rem', color: '#475569', marginTop: '0.5rem' }}>The seamless journey from ink on paper to structured, verified insights.</p>
            </div>
            
            <div className="pipeline-flow reveal" style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'center', maxWidth: '900px', margin: '3rem auto 0' }}>
              {/* SVG Wavy Connector Line */}
              <svg style={{ position: 'absolute', top: '1.75rem', left: '5%', width: '90%', height: '40px', zIndex: 1, pointerEvents: 'none' }}>
                <path d="M 10 20 C 150 45, 200 -5, 330 20 C 460 45, 510 -5, 640 20 C 770 45, 800 -5, 950 20" fill="none" stroke="#a5b4fc" strokeWidth="2.5" strokeDasharray="6,6" />
              </svg>

              {[
                { icon: 'document_scanner', label: 'Scan', sub: 'Capture high-res imagery' },
                { icon: 'grid_view', label: 'Segmentation', sub: 'Isolating regions of interest' },
                { icon: 'text_fields', label: 'OCR', sub: 'Multi-model text extraction' },
                { icon: 'psychology', label: 'AI Scoring', sub: 'Contextual semantic evaluation', featured: true },
                { icon: 'picture_as_pdf', label: 'Report', sub: 'Verified academic transcript' },
              ].map((node, i) => (
                <div key={i} className="pipeline-node" style={{ position: 'relative', zIndex: 2 }}>
                  <div className={`pipeline-node-icon${node.featured ? ' featured' : ''}`} style={node.featured ? { background: '#6366f1', color: '#ffffff', borderColor: '#6366f1' } : {}}>
                    <span className="material-symbols-outlined" style={node.featured ? { fontVariationSettings: "'FILL' 1" } : {}}>{node.icon}</span>
                  </div>
                  <div className="pipeline-node-label" style={{ fontWeight: 700, marginTop: '0.75rem', color: '#0f172a' }}>{node.label}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Feature Highlights ── */}
        <section className="section" id="features" style={{ background: 'transparent', padding: '5rem 2rem' }}>
          <div className="section-inner" style={{ maxWidth: '1200px', margin: '0 auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2rem' }}>
              
              {/* Multi-OCR (1 col) */}
              <div className="feature-card reveal" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'space-between', minHeight: '340px', transitionDelay: '0ms' }}>
                <div style={{ width: '100%' }}>
                  <div className="feature-icon">
                    <span className="material-symbols-outlined">translate</span>
                  </div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.75rem' }}>Multi-OCR Support</h3>
                  <p style={{ fontSize: '0.925rem', color: '#64748b', lineHeight: 1.6 }}>Support wxl OCR support can snal answer togliles and technology.</p>
                </div>
                <div className="feature-tags" style={{ display: 'flex', gap: '0.5rem', marginTop: '1.5rem' }}>
                  {['Technology', 'AMSK', 'SSS'].map(tag => (
                    <span key={tag} className="feature-tag" style={{ background: '#e0d7ff', color: '#4f46e5', fontWeight: 700 }}>{tag}</span>
                  ))}
                </div>
              </div>

              {/* Rubric-based (1 col) */}
              <div className="feature-card reveal" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'space-between', minHeight: '340px', transitionDelay: '150ms' }}>
                <div style={{ width: '100%' }}>
                  <div className="feature-icon">
                    <span className="material-symbols-outlined">rule</span>
                  </div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.75rem' }}>Rubric-Based Grading</h3>
                  <p style={{ fontSize: '0.925rem', color: '#64748b', lineHeight: 1.6 }}>Mini score bars in narroited grading.</p>
                </div>
                <div className="score-bars" style={{ width: '100%', marginTop: '1.5rem' }}>
                  <div className="score-bar-row" style={{ marginBottom: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 700, color: '#475569' }}>
                      <span>Mini Score</span>
                      <span>70</span>
                    </div>
                    <div className="score-bar-track"><div className="score-bar-fill" style={{ width: '70%', background: '#6366f1' }} /></div>
                  </div>
                  <div className="score-bar-row">
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 700, color: '#475569' }}>
                      <span>East Score</span>
                      <span>60</span>
                    </div>
                    <div className="score-bar-track"><div className="score-bar-fill" style={{ width: '60%', background: '#6366f1' }} /></div>
                  </div>
                </div>
              </div>

              {/* Instant Analytics (1 col) */}
              <div className="feature-card reveal" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'space-between', minHeight: '340px', transitionDelay: '300ms' }}>
                <div style={{ width: '100%' }}>
                  <div className="feature-icon">
                    <span className="material-symbols-outlined">monitoring</span>
                  </div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.75rem' }}>Instant Analytics</h3>
                  <p style={{ fontSize: '0.925rem', color: '#64748b', lineHeight: 1.6 }}>Stat tiles and straty Instant analytics.</p>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', width: '100%', marginTop: '1.5rem' }}>
                  {[
                    { val: '99%', label: 'Stats' },
                    { val: '12.4s', label: 'Avg Time' },
                    { val: '850k', label: 'Papers' }
                  ].map((tile, idx) => (
                    <div key={idx} style={{
                      flex: 1,
                      background: 'rgba(99, 102, 241, 0.06)',
                      border: '1px solid rgba(99, 102, 241, 0.12)',
                      borderRadius: '8px',
                      padding: '0.75rem 0.25rem',
                      textAlign: 'center'
                    }}>
                      <div style={{ fontSize: '1.125rem', fontWeight: 800, color: '#4f46e5' }}>{tile.val}</div>
                      <div style={{ fontSize: '0.625rem', color: '#64748b', fontWeight: 600, marginTop: '2px' }}>{tile.label}</div>
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
        <Footer />
      </main>
    </>
  );
}
