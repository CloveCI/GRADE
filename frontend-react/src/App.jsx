import { Routes, Route, Navigate } from 'react-router-dom';
import LandingPage   from './pages/LandingPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage    from './pages/UploadPage';
import EvaluatorPage from './pages/EvaluatorPage';
import ReportsPage   from './pages/ReportsPage';
import SettingsPage  from './pages/SettingsPage';

export default function App() {
  return (
    <Routes>
      <Route path="/"          element={<LandingPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/upload"    element={<UploadPage />} />
      <Route path="/evaluator" element={<EvaluatorPage />} />
      <Route path="/reports"   element={<ReportsPage />} />
      <Route path="/settings"  element={<SettingsPage />} />
      {/* Catch-all → landing */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
