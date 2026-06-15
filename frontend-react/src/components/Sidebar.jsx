import { NavLink, useNavigate } from 'react-router-dom';

const NAV = [
  { id: 'dashboard', label: 'Dashboard',  icon: 'dashboard',    to: '/dashboard'  },
  { id: 'upload',    label: 'Processing', icon: 'cloud_upload',  to: '/upload'     },
  { id: 'evaluator', label: 'Evaluator',  icon: 'visibility',   to: '/evaluator'  },
  { id: 'reports',   label: 'Reports',    icon: 'description',  to: '/reports'    },
  { id: 'settings',  label: 'Settings',   icon: 'settings',     to: '/settings'   },
];

export default function Sidebar() {
  const navigate = useNavigate();

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1", fontSize: '1.125rem' }}>school</span>
        </div>
        <div className="sidebar-brand-text">
          <h1>GRADE</h1>
          <p>Institutional Portal</p>
        </div>
      </div>

      <div style={{ padding: '0 1rem 0.75rem' }}>
        <button className="sidebar-new-btn" onClick={() => navigate('/upload')}>
          <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>add_circle</span>
          New Evaluation
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
        <a href="#">
          <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>help</span>
          Help Center
        </a>
        <a href="#">
          <span className="material-symbols-outlined" style={{ fontSize: '1.125rem' }}>account_circle</span>
          Account
        </a>
      </div>
    </aside>
  );
}
