export default function Topbar({ title, showStatus = true }) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <h2>{title}</h2>
        {showStatus && (
          <div className="status-badge">
            <div className="status-dot" />
            <span>System Active</span>
          </div>
        )}
      </div>
      <div className="topbar-actions">
        <div className="topbar-search">
          <span className="material-symbols-outlined">search</span>
          <input
            type="text"
            placeholder="Search papers, students…"
            id="global-search"
            aria-label="Global search"
          />
        </div>
        <button className="icon-btn" title="Notifications" aria-label="Notifications">
          <span className="material-symbols-outlined">notifications</span>
          <div className="notif-badge" />
        </button>
        <div className="avatar" title="Account">MD</div>
      </div>
    </header>
  );
}
