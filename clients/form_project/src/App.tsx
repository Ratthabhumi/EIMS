import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/auth/LoginPage';
import AdminDashboard from './pages/admin/AdminDashboard';
import CreateTraining from './pages/admin/CreateTraining';
import EditTraining from './pages/admin/EditTraining';
import TrainingDetails from './pages/admin/TrainingDetails';
import AssessmentForm from './pages/employee/AssessmentForm';
import SuccessPage from './pages/employee/SuccessPage';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/assessment/:id" element={<AssessmentForm />} />
          <Route path="/success" element={<SuccessPage />} />

          {/* Protected admin routes */}
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/admin" replace />} />
            <Route path="admin" element={
              <ProtectedRoute><AdminDashboard /></ProtectedRoute>
            } />
            <Route path="admin/trainings/new" element={
              <ProtectedRoute><CreateTraining /></ProtectedRoute>
            } />
            <Route path="admin/trainings/:id" element={
              <ProtectedRoute><TrainingDetails /></ProtectedRoute>
            } />
            <Route path="admin/trainings/:id/edit" element={
              <ProtectedRoute><EditTraining /></ProtectedRoute>
            } />
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
