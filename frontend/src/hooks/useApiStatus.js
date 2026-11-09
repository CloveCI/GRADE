import { useState, useEffect, useCallback } from 'react';
import { checkApiHealth } from '../lib/api';

/** Shared API connectivity state for Topbar and pages. */
export function useApiStatus(pollMs = 30000) {
  const [apiOk, setApiOk] = useState(null);

  const refresh = useCallback(async () => {
    const ok = await checkApiHealth();
    setApiOk(ok);
    return ok;
  }, []);

  const markConnected = useCallback(() => setApiOk(true), []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ok = await checkApiHealth();
      if (!cancelled) setApiOk(ok);
    })();
    const iv = pollMs > 0 ? setInterval(() => { refresh(); }, pollMs) : undefined;
    return () => {
      cancelled = true;
      if (iv) clearInterval(iv);
    };
  }, [pollMs, refresh]);

  return { apiOk, refresh, markConnected };
}
