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
        <button className="icon-btn" title="Notifications" aria-label="Notifications">
          <span className="material-symbols-outlined">notifications</span>
          <div className="notif-badge" />
        </button>
        <div className="profile-bubble" title="Account">
          <span style={{ fontSize: '0.8125rem', color: '#94a3b8', marginRight: '0.25rem' }}>Welcome,</span>
          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#f1f5f9' }}>Dr. Sarah Chen</span>
          <div className="avatar" style={{ marginLeft: '0.5rem' }}>SC</div>
        </div>
      </div>
    </header>
  );
}
