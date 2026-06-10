export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div>
          <div className="footer-brand">GRADE AI</div>
          <div className="footer-copy">© 2024 GRADE AI. Academic Integrity Guaranteed.</div>
        </div>
        <div className="footer-links">
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
          <a href="#">Security</a>
          <a href="#">Contact</a>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <div className="icon-btn" style={{ background: '#f1f5f9' }}>
            <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>public</span>
          </div>
          <div className="icon-btn" style={{ background: '#f1f5f9' }}>
            <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>mail</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
