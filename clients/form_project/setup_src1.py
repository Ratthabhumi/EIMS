import os

files = {
    'src/index.css': '''@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply antialiased text-microsoft-dark bg-microsoft-gray min-h-screen;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  }
}
''',

    'src/types/index.ts': '''export interface Training {
  id: string;
  title: string;
  description?: string;
  trainer: string;
  location: string;
  date: string;
  qrCode?: string;
}

export interface Response {
  id: string;
  trainingId: string;
  employeeId: string;
  fullName: string;
  department: string;
  q1: number;
  q2: number;
  q3: number;
  q4: number;
  q5: number;
  comment?: string;
  submittedAt: string;
}
''',

    'src/utils/api.ts': '''export const API_URL = '/api';

export const fetchTrainings = async () => {
  const res = await fetch(`${API_URL}/trainings`);
  return res.json();
};

export const fetchTraining = async (id: string) => {
  const res = await fetch(`${API_URL}/trainings/${id}`);
  if (!res.ok) throw new Error('Not found');
  return res.json();
};

export const createTraining = async (data: any) => {
  const res = await fetch(`${API_URL}/trainings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
};

export const fetchResponses = async (id: string) => {
  const res = await fetch(`${API_URL}/trainings/${id}/responses`);
  return res.json();
};

export const submitAssessment = async (data: any) => {
  const res = await fetch(`${API_URL}/assessments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
};
''',

    'src/main.tsx': '''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
''',

    'src/components/Layout.tsx': '''import { Outlet, Link, useLocation } from 'react-router-dom';
import { BookOpen } from 'lucide-react';

export default function Layout() {
  const location = useLocation();
  const isAdmin = location.pathname.startsWith('/admin');

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-microsoft-blue text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <BookOpen className="w-6 h-6" />
            <span className="font-semibold text-lg">Training Assessment System</span>
          </div>
          {isAdmin && (
            <nav>
              <Link to="/admin" className="text-white hover:text-blue-200 px-3 py-2 rounded-md text-sm font-medium">
                Admin Dashboard
              </Link>
            </nav>
          )}
        </div>
      </header>
      
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
      
      <footer className="bg-white border-t border-gray-200 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-center">
          <p className="text-sm text-gray-500">&copy; {new Date().getFullYear()} Microsoft Onsite Training Assessment System</p>
        </div>
      </footer>
    </div>
  );
}
''',

    'src/App.tsx': '''import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import AdminDashboard from './pages/admin/AdminDashboard';
import CreateTraining from './pages/admin/CreateTraining';
import TrainingDetails from './pages/admin/TrainingDetails';
import AssessmentForm from './pages/employee/AssessmentForm';
import SuccessPage from './pages/employee/SuccessPage';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/admin" replace />} />
          <Route path="admin" element={<AdminDashboard />} />
          <Route path="admin/trainings/new" element={<CreateTraining />} />
          <Route path="admin/trainings/:id" element={<TrainingDetails />} />
          
          <Route path="assessment/:id" element={<AssessmentForm />} />
          <Route path="success" element={<SuccessPage />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
'''
}

for filepath, content in files.items():
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print('Frontend core files created')
