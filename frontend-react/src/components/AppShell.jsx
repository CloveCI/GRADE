import Sidebar from './Sidebar';
import Topbar from './Topbar';
import Footer from './Footer';

/**
 * AppShell wraps all authenticated app pages with Sidebar + Topbar + Footer.
 * @param {string} title - Topbar page title
 * @param {boolean} showStatus - Show the "System Active" badge
 * @param {boolean} showFooter - Show the footer
 * @param {boolean} overflow - Control overflow on main-content
 */
export default function AppShell({ title, showStatus = true, showFooter = true, overflow = true, children }) {
  return (
    <div className="app-shell portal-dark">
      <Sidebar />
      <div className="main-content" style={overflow ? {} : { overflow: 'hidden' }}>
        <Topbar title={title} showStatus={showStatus} />
        {children}
        {showFooter && <Footer />}
      </div>
    </div>
  );
}
