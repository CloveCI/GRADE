import { useEffect, useState } from 'react';
import { useApiStatus } from '../hooks/useApiStatus';

export default function Topbar({ title, showStatus = true }) {
  const { apiOk } = useApiStatus();

  return (
    <header className="topbar">
      <div className="topbar-title">
        <h2>{title}</h2>
        {showStatus && (
          <div className="status-badge" title={apiOk === null ? 'Checking…' : apiOk ? 'Ready to grade' : 'Service unavailable'}>
            <div className="status-dot" style={apiOk === false ? { background: '#f59e0b' } : undefined} />
            <span>{apiOk === null ? 'Connecting…' : apiOk ? 'System ready' : 'Offline'}</span>
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
