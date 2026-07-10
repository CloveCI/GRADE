import { NavLink, useNavigate, Link } from 'react-router-dom';

const NAV = [
  { id: 'dashboard', label: 'Dashboard',  icon: 'dashboard',    to: '/dashboard'  },
  { id: 'upload',    label: 'Submit papers', icon: 'cloud_upload', to: '/processing' },
  { id: 'evaluator', label: 'Review grades', icon: 'grading',      to: '/evaluator'  },
  { id: 'reports',   label: 'Reports',    icon: 'description',  to: '/reports'    },
  { id: 'inspect',   label: 'Inspect',    icon: 'search',       to: '/inspect'    },
  { id: 'settings',  label: 'Settings',   icon: 'settings',     to: '/settings'   },
];

export default function Sidebar() {
  const navigate = useNavigate();

  return (
    <aside className="sidebar">
      <Link to="/" className="sidebar-brand" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
        <div className="sidebar-brand-icon">
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1", fontSize: '1.125rem' }}>school</span>
        </div>
        <div className="sidebar-brand-text">
          <h1>GRADE</h1>
          <p>GRADING PORTAL</p>
        </div>
      </Link>

      <div style={{ padding: '0 1rem 0.75rem' }}>
        <button type="button" className="sidebar-new-btn" onClick={() => navigate('/processing')}>
          <span className="material-symbols-outlined" style={{ fontSize: '1.25rem' }}>add</span>
          Grade papers
        </button>
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ id, label, icon, to }) => (
          <NavLink
            key={id}
            to={to}
            className={({ isActive }) => isActive ? 'active' : ''}
          >
            {({ isActive }) => (
              <>
                <span
                  className="material-symbols-outlined"
                  style={isActive ? { fontVariationSettings: "'FILL' 1" } : {}}
                >
                  {icon}
                </span>
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <Link to="/docs">
          <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>help</span>
          Help
        </Link>
        <a href="#">
          <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>account_circle</span>
          Account
        </a>
      </div>
    </aside>
  );
}
