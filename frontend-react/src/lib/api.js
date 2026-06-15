// Shared API utilities — ported from shared.js

const API_BASE = import.meta.env.VITE_API_URL;

export async function apiFetch(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[GRADE] API unavailable (${endpoint}):`, err.message);
    return null;
  }
}

export async function checkApiHealth() {
  try {
    const r = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}

export async function getExams() {
  console.log('Calling /api/exams');
  return apiFetch('/api/exams');
}
