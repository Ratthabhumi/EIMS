import os

files = {
    'src/types/index.ts': '''export interface Training {
  id: string;
  title: string;
  description?: string;
  trainer: string;
  location: string;
  date: string;
  qrCode?: string;
}

export interface Question {
  id: string;
  label: string;
  isActive: number;
  orderIndex: number;
}

export interface Answer {
  questionId: string;
  label: string;
  score: number;
}

export interface Response {
  id: string;
  trainingId: string;
  employeeId: string;
  fullName: string;
  department: string;
  answers: string; // JSON string of Answer[]
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
  if (!res.ok) throw new Error('Failed to submit');
  return res.json();
};

export const fetchQuestions = async () => {
  const res = await fetch(`${API_URL}/questions`);
  return res.json();
};

export const createQuestion = async (data: any) => {
  const res = await fetch(`${API_URL}/questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
};

export const updateQuestion = async (id: string, data: any) => {
  const res = await fetch(`${API_URL}/questions/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
};

export const deleteQuestion = async (id: string) => {
  const res = await fetch(`${API_URL}/questions/${id}`, {
    method: 'DELETE',
  });
  return res.json();
};
''',

    'src/components/Layout.tsx': '''import { Outlet, Link, useLocation } from 'react-router-dom';
import { BookOpen, Settings } from 'lucide-react';

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
            <nav className="flex items-center space-x-4">
              <Link to="/admin" className="text-white hover:text-blue-200 px-3 py-2 rounded-md text-sm font-medium">
                Dashboard
              </Link>
              <Link to="/admin/questions" className="text-white hover:text-blue-200 px-3 py-2 rounded-md text-sm font-medium flex items-center gap-1">
                <Settings className="w-4 h-4" /> Questions
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
import ManageQuestions from './pages/admin/ManageQuestions';
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
          <Route path="admin/questions" element={<ManageQuestions />} />
          
          <Route path="assessment/:id" element={<AssessmentForm />} />
          <Route path="success" element={<SuccessPage />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
''',
    
    'src/pages/admin/CreateTraining.tsx': '''import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createTraining } from '../../utils/api';

export default function CreateTraining() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    
    const formData = new FormData(e.currentTarget);
    const data = {
      id: crypto.randomUUID(),
      title: formData.get('title'),
      description: formData.get('description'),
      trainer: formData.get('trainer'),
      location: formData.get('location'),
      date: formData.get('date'),
      origin: window.location.origin
    };

    try {
      const res = await createTraining(data);
      navigate(`/admin/trainings/${res.id}`);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="md:flex md:items-center md:justify-between mb-6">
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
            Create New Training
          </h2>
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700">Training Title</label>
            <input required type="text" name="title" id="title" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
          </div>

          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700">Description</label>
            <textarea name="description" id="description" rows={3} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm"></textarea>
          </div>

          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="trainer" className="block text-sm font-medium text-gray-700">Trainer Name</label>
              <input required type="text" name="trainer" id="trainer" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>

            <div>
              <label htmlFor="location" className="block text-sm font-medium text-gray-700">Location / Room</label>
              <input required type="text" name="location" id="location" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
            
            <div>
              <label htmlFor="date" className="block text-sm font-medium text-gray-700">Date</label>
              <input required type="date" name="date" id="date" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
          </div>

          <div className="flex justify-end mt-6 pt-5 border-t border-gray-200">
            <button
              type="button"
              onClick={() => navigate('/admin')}
              className="bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-microsoft-blue"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="ml-3 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-microsoft-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-microsoft-blue"
            >
              {loading ? 'Saving...' : 'Save Training'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
''',

    'src/pages/admin/TrainingDetails.tsx': '''import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { Download, ArrowLeft } from 'lucide-react';
import { fetchTraining, fetchResponses, API_URL } from '../../utils/api';
import { Training, Response, Answer } from '../../types';

export default function TrainingDetails() {
  const { id } = useParams<{ id: string }>();
  const [training, setTraining] = useState<Training | null>(null);
  const [responses, setResponses] = useState<Response[]>([]);

  useEffect(() => {
    if (id) {
      fetchTraining(id).then(setTraining).catch(console.error);
      fetchResponses(id).then(setResponses).catch(console.error);
    }
  }, [id]);

  const calculateAvg = (answersStr: string) => {
    try {
      const answers: Answer[] = JSON.parse(answersStr);
      if (answers.length === 0) return 0;
      const sum = answers.reduce((acc, curr) => acc + Number(curr.score), 0);
      return (sum / answers.length).toFixed(1);
    } catch {
      return 0;
    }
  };

  if (!training) return <div className="text-center py-12">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <Link to="/admin" className="mr-4 text-gray-400 hover:text-gray-600">
            <ArrowLeft className="h-6 w-6" />
          </Link>
          <h1 className="text-2xl font-semibold text-gray-900">{training.title}</h1>
        </div>
        <a
          href={`${API_URL}/trainings/${id}/export`}
          className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        >
          <Download className="-ml-1 mr-2 h-5 w-5 text-gray-400" />
          Export to Excel
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900">Training Information</h3>
            </div>
            <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
              <dl className="sm:divide-y sm:divide-gray-200">
                <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500">Trainer</dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{training.trainer}</dd>
                </div>
                <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500">Location</dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{training.location}</dd>
                </div>
                <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500">Date</dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">{training.date}</dd>
                </div>
              </dl>
            </div>
          </div>

          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6 flex justify-between items-center">
              <h3 className="text-lg leading-6 font-medium text-gray-900">Recent Responses ({responses.length})</h3>
            </div>
            <div className="border-t border-gray-200">
              {responses.length > 0 ? (
                <ul className="divide-y divide-gray-200">
                  {responses.map((res) => (
                    <li key={res.id} className="px-4 py-4 sm:px-6">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm font-medium text-microsoft-blue">{res.fullName} ({res.employeeId})</p>
                        <div className="ml-2 flex-shrink-0 flex">
                          <p className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                            Avg Score: {calculateAvg(res.answers)}
                          </p>
                        </div>
                      </div>
                      <div className="text-sm text-gray-500">
                        <p>Department: {res.department}</p>
                        {res.comment && <p className="mt-1 italic">"{res.comment}"</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 py-8 text-center text-gray-500">No responses yet.</div>
              )}
            </div>
          </div>
        </div>

        <div className="md:col-span-1">
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
              <h3 className="text-lg leading-6 font-medium text-gray-900 text-center">Assessment QR Code</h3>
            </div>
            <div className="p-6 flex flex-col items-center justify-center space-y-4">
              <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
                <QRCodeSVG value={training.qrCode || ''} size={200} />
              </div>
              <p className="text-sm text-center text-gray-500 mt-4">
                Scan this code to fill out the assessment form.
              </p>
              <a 
                href={training.qrCode} 
                target="_blank" 
                rel="noreferrer"
                className="text-microsoft-blue text-sm hover:underline break-all text-center"
              >
                {training.qrCode}
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
''',

    'src/pages/admin/ManageQuestions.tsx': '''import { useEffect, useState } from 'react';
import { Plus, Trash2, Edit2, Save, X } from 'lucide-react';
import { fetchQuestions, createQuestion, updateQuestion, deleteQuestion } from '../../utils/api';
import { Question } from '../../types';

export default function ManageQuestions() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState('');
  
  const [newLabel, setNewLabel] = useState('');

  const loadQuestions = async () => {
    try {
      const data = await fetchQuestions();
      setQuestions(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadQuestions();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLabel.trim()) return;
    try {
      await createQuestion({
        id: crypto.randomUUID(),
        label: newLabel.trim(),
        isActive: 1,
        orderIndex: questions.length + 1
      });
      setNewLabel('');
      loadQuestions();
    } catch (e) {
      console.error(e);
    }
  };

  const startEdit = (q: Question) => {
    setEditingId(q.id);
    setEditLabel(q.label);
  };

  const handleUpdate = async (q: Question) => {
    if (!editLabel.trim()) return;
    try {
      await updateQuestion(q.id, {
        label: editLabel.trim(),
        isActive: q.isActive,
        orderIndex: q.orderIndex
      });
      setEditingId(null);
      loadQuestions();
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleActive = async (q: Question) => {
    try {
      await updateQuestion(q.id, {
        label: q.label,
        isActive: q.isActive === 1 ? 0 : 1,
        orderIndex: q.orderIndex
      });
      loadQuestions();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this question? This will not affect existing responses, but the question will be removed for future ones.')) return;
    try {
      await deleteQuestion(id);
      loadQuestions();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-gray-900">Manage Evaluation Topics</h1>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg p-6">
        <form onSubmit={handleAdd} className="flex gap-4 items-end mb-8">
          <div className="flex-1">
            <label htmlFor="newLabel" className="block text-sm font-medium text-gray-700">Add New Question</label>
            <input 
              type="text" 
              id="newLabel" 
              value={newLabel}
              onChange={e => setNewLabel(e.target.value)}
              placeholder="e.g. Rate the clarity of the presentation"
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" 
            />
          </div>
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-microsoft-blue hover:bg-blue-700"
          >
            <Plus className="-ml-1 mr-2 h-5 w-5" />
            Add
          </button>
        </form>

        <h3 className="text-lg font-medium text-gray-900 mb-4 border-b pb-2">Current Questions</h3>
        <ul className="space-y-4">
          {questions.map((q, idx) => (
            <li key={q.id} className="flex items-center justify-between bg-gray-50 p-4 rounded-md border border-gray-200">
              {editingId === q.id ? (
                <div className="flex-1 flex gap-2 mr-4">
                  <input 
                    type="text" 
                    value={editLabel}
                    onChange={e => setEditLabel(e.target.value)}
                    className="block w-full border border-gray-300 rounded-md shadow-sm py-1 px-2 focus:outline-none focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" 
                  />
                  <button onClick={() => handleUpdate(q)} className="text-green-600 hover:text-green-800 p-1">
                    <Save className="h-5 w-5" />
                  </button>
                  <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-600 p-1">
                    <X className="h-5 w-5" />
                  </button>
                </div>
              ) : (
                <div className="flex-1 flex items-center">
                  <span className="font-medium text-gray-500 w-8">{idx + 1}.</span>
                  <span className={`flex-1 ${q.isActive === 0 ? 'text-gray-400 line-through' : 'text-gray-900'}`}>
                    {q.label}
                  </span>
                </div>
              )}
              
              {editingId !== q.id && (
                <div className="flex items-center space-x-3 ml-4">
                  <label className="flex items-center cursor-pointer text-sm text-gray-600">
                    <input 
                      type="checkbox" 
                      checked={q.isActive === 1}
                      onChange={() => handleToggleActive(q)}
                      className="mr-2 h-4 w-4 text-microsoft-blue rounded border-gray-300 focus:ring-microsoft-blue"
                    />
                    Active
                  </label>
                  <div className="h-4 w-px bg-gray-300"></div>
                  <button onClick={() => startEdit(q)} className="text-gray-500 hover:text-microsoft-blue p-1">
                    <Edit2 className="h-4 w-4" />
                  </button>
                  <button onClick={() => handleDelete(q.id)} className="text-gray-500 hover:text-red-600 p-1">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              )}
            </li>
          ))}
          {questions.length === 0 && (
            <li className="text-center text-gray-500 py-4">No evaluation topics defined yet.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
''',

    'src/pages/employee/AssessmentForm.tsx': '''import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchTraining, submitAssessment, fetchQuestions } from '../../utils/api';
import { Training, Question, Answer } from '../../types';

export default function AssessmentForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [training, setTraining] = useState<Training | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (id) {
      fetchTraining(id).then(setTraining).catch(() => setError('Training session not found.'));
      fetchQuestions().then(data => {
        // Only show active questions
        setQuestions(data.filter((q: Question) => q.isActive === 1));
      }).catch(console.error);
    }
  }, [id]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    
    const formData = new FormData(e.currentTarget);
    
    const answers: Answer[] = questions.map(q => ({
      questionId: q.id,
      label: q.label,
      score: Number(formData.get(q.id))
    }));

    const data = {
      id: crypto.randomUUID(),
      trainingId: id,
      employeeId: formData.get('employeeId'),
      fullName: formData.get('fullName'),
      department: formData.get('department'),
      answers: answers,
      comment: formData.get('comment'),
      submittedAt: new Date().toISOString()
    };

    try {
      await submitAssessment(data);
      navigate('/success');
    } catch (err) {
      console.error(err);
      setError('Failed to submit. Please try again.');
      setLoading(false);
    }
  };

  if (error) {
    return (
      <div className="max-w-xl mx-auto mt-12 bg-red-50 border border-red-200 text-red-700 p-6 rounded-lg shadow-sm text-center">
        <h2 className="text-xl font-bold mb-2">Error</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!training) {
    return <div className="text-center py-12">Loading form...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto bg-white shadow overflow-hidden sm:rounded-lg mb-12">
      <div className="px-4 py-5 sm:px-6 bg-microsoft-blue text-white">
        <h3 className="text-xl leading-6 font-semibold">Training Assessment Form</h3>
        <p className="mt-1 max-w-2xl text-sm opacity-90">Please fill out the evaluation for this session.</p>
      </div>
      
      <div className="border-t border-gray-200 px-4 py-5 sm:p-6 bg-gray-50">
        <div className="mb-4 pb-4 border-b border-gray-200">
          <p className="text-sm font-medium text-gray-500">Training Session</p>
          <p className="text-lg font-bold text-gray-900">{training.title}</p>
          <p className="text-sm text-gray-600">Date: {training.date}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="employeeId" className="block text-sm font-medium text-gray-700">Employee ID *</label>
              <input required type="text" name="employeeId" id="employeeId" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-gray-700">Full Name *</label>
              <input required type="text" name="fullName" id="fullName" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="department" className="block text-sm font-medium text-gray-700">Department *</label>
              <input required type="text" name="department" id="department" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm" />
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200">
            <h4 className="text-lg font-medium text-gray-900 mb-4">Evaluation (1 = Poor, 5 = Excellent)</h4>
            <div className="space-y-6">
              {questions.length === 0 && (
                <p className="text-sm text-gray-500 italic">No evaluation topics have been configured yet.</p>
              )}
              {questions.map((q, index) => (
                <div key={q.id}>
                  <label className="block text-sm font-medium text-gray-700 mb-2">{index + 1}. {q.label} *</label>
                  <div className="flex items-center space-x-6">
                    {[1, 2, 3, 4, 5].map((rating) => (
                      <label key={rating} className="flex items-center cursor-pointer hover:bg-gray-100 p-1 rounded-md">
                        <input required type="radio" name={q.id} value={rating} className="h-4 w-4 text-microsoft-blue border-gray-300 focus:ring-microsoft-blue" />
                        <span className="ml-2 text-sm text-gray-700 font-medium">{rating}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-6 border-t border-gray-200">
            <label htmlFor="comment" className="block text-sm font-medium text-gray-700">Additional Comments (Optional)</label>
            <textarea name="comment" id="comment" rows={4} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-microsoft-blue focus:border-microsoft-blue sm:text-sm"></textarea>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={loading || questions.length === 0}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-microsoft-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-microsoft-blue disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Submitting...' : 'Submit Assessment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
'''
}

for filepath, content in files.items():
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print('Frontend pages updated successfully')
