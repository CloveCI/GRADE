import { Routes, Route, Navigate } from 'react-router-dom';
import LandingPage   from './pages/LandingPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage    from './pages/UploadPage';
import EvaluatorPage from './pages/EvaluatorPage';
import ReportsPage   from './pages/ReportsPage';
import SettingsPage  from './pages/SettingsPage';
import DocsPage      from './pages/DocsPage';
import ExamDetailPage from './pages/ExamDetailPage';
import InspectPage   from './pages/InspectPage';

export default function App() {
  return (
    <Routes>
      <Route path="/"          element={<LandingPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/processing" element={<UploadPage />} />
      <Route path="/upload" element={<Navigate to="/processing" replace />} />
      <Route path="/evaluator" element={<EvaluatorPage />} />
      <Route path="/exams/:examId" element={<ExamDetailPage />} />
      <Route path="/inspect" element={<InspectPage />} />
      <Route path="/reports"   element={<ReportsPage />} />
      <Route path="/docs"      element={<DocsPage />} />
      <Route path="/settings"  element={<SettingsPage />} />
      {/* Catch-all → landing */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
