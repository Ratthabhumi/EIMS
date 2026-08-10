import os

# Delete ManageQuestions
try:
    os.remove('src/pages/admin/ManageQuestions.tsx')
except OSError:
    pass

files = {
    'src/App.tsx': '''import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import AdminDashboard from './pages/admin/AdminDashboard';
import CreateTraining from './pages/admin/CreateTraining';
import EditTraining from './pages/admin/EditTraining';
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
          <Route path="admin/trainings/:id/edit" element={<EditTraining />} />
          
          <Route path="assessment/:id" element={<AssessmentForm />} />
          <Route path="success" element={<SuccessPage />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
''',

    'src/components/Layout.tsx': '''import { Outlet, Link, useLocation } from 'react-router-dom';
import { BookOpen } from 'lucide-react';

export default function Layout() {
  const location = useLocation();
  const isAdmin = location.pathname.startsWith('/admin');

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-brand-blue text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <BookOpen className="w-6 h-6" />
            <span className="font-semibold text-lg">Onsite Training Assessment System</span>
          </div>
          {isAdmin && (
            <nav className="flex items-center space-x-4">
              <Link to="/admin" className="text-white hover:text-blue-200 px-3 py-2 rounded-md text-sm font-medium">
                Dashboard
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
          <p className="text-sm text-gray-500">&copy; {new Date().getFullYear()} Onsite Training Assessment System</p>
        </div>
      </footer>
    </div>
  );
}
''',

    'src/pages/admin/CreateTraining.tsx': '''import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createTraining } from '../../utils/api';
import { Question } from '../../types';
import { Plus, Trash2 } from 'lucide-react';

export default function CreateTraining() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [newLabel, setNewLabel] = useState('');
  
  // Default questions
  const [questions, setQuestions] = useState<Question[]>([
    { id: crypto.randomUUID(), label: '1. Training Content Quality', isActive: 1, orderIndex: 1 },
    { id: crypto.randomUUID(), label: '2. Trainer Performance & Knowledge', isActive: 1, orderIndex: 2 },
    { id: crypto.randomUUID(), label: '3. Knowledge and Skills Gained', isActive: 1, orderIndex: 3 },
    { id: crypto.randomUUID(), label: '4. Training Materials and Resources', isActive: 1, orderIndex: 4 },
    { id: crypto.randomUUID(), label: '5. Overall Satisfaction', isActive: 1, orderIndex: 5 }
  ]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    
    const formData = new FormData(e.currentTarget);
    const data = {
      title: formData.get('title'),
      description: formData.get('description'),
      trainer: formData.get('trainer'),
      location: formData.get('location'),
      date: formData.get('date'),
      origin: window.location.origin,
      questions: questions
    };

    try {
      const res = await createTraining(data);
      navigate(`/admin/trainings/${res.id}`);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  const addQuestion = () => {
    if (!newLabel.trim()) return;
    setQuestions([...questions, {
      id: crypto.randomUUID(),
      label: newLabel.trim(),
      isActive: 1,
      orderIndex: questions.length
    }]);
    setNewLabel('');
  };

  const removeQuestion = (qId: string) => {
    setQuestions(questions.filter(q => q.id !== qId));
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="md:flex md:items-center md:justify-between mb-6">
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
            Create New Training
          </h2>
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <h3 className="text-lg font-medium text-gray-900 border-b pb-2">Training Details</h3>

          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700">Training Title</label>
            <input required type="text" name="title" id="title" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
          </div>

          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700">Description</label>
            <textarea name="description" id="description" rows={3} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm"></textarea>
          </div>

          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="trainer" className="block text-sm font-medium text-gray-700">Trainer Name</label>
              <input required type="text" name="trainer" id="trainer" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>

            <div>
              <label htmlFor="location" className="block text-sm font-medium text-gray-700">Location / Room</label>
              <input required type="text" name="location" id="location" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
            
            <div>
              <label htmlFor="date" className="block text-sm font-medium text-gray-700">Date</label>
              <input required type="date" name="date" id="date" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
          </div>

          <div className="mt-8">
            <h3 className="text-lg font-medium text-gray-900 border-b pb-2 mb-4">Evaluation Topics for this Training</h3>
            <p className="text-sm text-gray-500 mb-4">You can customize the questions specifically for this session.</p>
            
            <ul className="space-y-3 mb-4">
              {questions.map((q, idx) => (
                <li key={q.id} className="flex items-center justify-between bg-gray-50 p-3 rounded-md border border-gray-200">
                  <span className="text-sm text-gray-900">{idx + 1}. {q.label}</span>
                  <button type="button" onClick={() => removeQuestion(q.id)} className="text-red-500 hover:text-red-700 p-1">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
              {questions.length === 0 && (
                <li className="text-sm text-gray-500 italic">No questions added yet.</li>
              )}
            </ul>

            <div className="flex gap-2">
              <input 
                type="text" 
                value={newLabel}
                onChange={e => setNewLabel(e.target.value)}
                placeholder="Add a new question..."
                className="flex-1 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" 
              />
              <button
                type="button"
                onClick={addQuestion}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
              >
                <Plus className="-ml-1 mr-1 h-5 w-5" /> Add
              </button>
            </div>
          </div>

          <div className="flex justify-end mt-6 pt-5 border-t border-gray-200">
            <button
              type="button"
              onClick={() => navigate('/admin')}
              className="bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="ml-3 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue"
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

    'server/routes/trainings.ts': '''import { Router } from 'express';
import dbPromise from '../database/db.js';
import * as xlsx from 'xlsx';
import crypto from 'crypto';

const router = Router();

router.get('/', async (req, res) => {
  const db = await dbPromise;
  const trainings = await db.all('SELECT * FROM Training ORDER BY date DESC');
  res.json(trainings);
});

router.post('/', async (req, res) => {
  const { title, description, trainer, location, date, origin, questions } = req.body;
  const db = await dbPromise;
  const id = crypto.randomUUID();
  const qrCode = `${origin || 'http://localhost:5173'}/assessment/${id}`;
  
  const questionsJson = JSON.stringify(questions || []);
  
  await db.run(
    'INSERT INTO Training (id, title, description, trainer, location, date, qrCode, questions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
    [id, title, description, trainer, location, date, qrCode, questionsJson]
  );
  res.json({ success: true, id });
});

router.put('/:id', async (req, res) => {
  const { title, description, trainer, location, date, questions } = req.body;
  const db = await dbPromise;
  
  const questionsJson = JSON.stringify(questions || []);

  await db.run(
    'UPDATE Training SET title = ?, description = ?, trainer = ?, location = ?, date = ?, questions = ? WHERE id = ?',
    [title, description, trainer, location, date, questionsJson, req.params.id]
  );
  res.json({ success: true });
});

router.get('/:id', async (req, res) => {
  const db = await dbPromise;
  const training = await db.get('SELECT * FROM Training WHERE id = ?', [req.params.id]);
  if (!training) {
    return res.status(404).json({ error: 'Training not found' });
  }
  res.json(training);
});

router.get('/:id/responses', async (req, res) => {
  const db = await dbPromise;
  const responses = await db.all('SELECT * FROM Responses WHERE trainingId = ? ORDER BY submittedAt DESC', [req.params.id]);
  res.json(responses);
});

router.get('/:id/export', async (req, res) => {
  const db = await dbPromise;
  const training = await db.get('SELECT * FROM Training WHERE id = ?', [req.params.id]);
  if (!training) {
    return res.status(404).json({ error: 'Training not found' });
  }

  const responses = await db.all('SELECT * FROM Responses WHERE trainingId = ? ORDER BY submittedAt ASC', [req.params.id]);
  
  const data = responses.map(r => {
    let answersObj: Record<string, any> = {};
    let totalScore = 0;
    let answerCount = 0;
    
    try {
      const parsedAnswers = JSON.parse(r.answers);
      parsedAnswers.forEach((ans: any) => {
        answersObj[ans.label] = ans.score;
        totalScore += Number(ans.score);
        answerCount++;
      });
    } catch (e) {
      // ignore
    }

    return {
      'Employee ID': r.employeeId,
      'Name': r.fullName,
      'Department': r.department,
      'Training': training.title,
      'Trainer': training.trainer,
      'Date': training.date,
      ...answersObj,
      'Average Score': answerCount > 0 ? (totalScore / answerCount).toFixed(2) : '0',
      'Comment': r.comment || '',
      'Submitted Time': new Date(r.submittedAt).toLocaleString()
    };
  });

  const ws = xlsx.utils.json_to_sheet(data);
  const wb = xlsx.utils.book_new();
  xlsx.utils.book_append_sheet(wb, ws, 'Responses');
  
  const buffer = xlsx.write(wb, { type: 'buffer', bookType: 'xlsx' });
  
  res.setHeader('Content-Disposition', `attachment; filename="Training_Responses_${req.params.id}.xlsx"`);
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.send(buffer);
});

export default router;
'''
}

for filepath, content in files.items():
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print('Updated plan successfully')
