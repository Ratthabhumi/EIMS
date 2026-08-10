import os
import sqlite3
import re

# 1. DB Migration
try:
    conn = sqlite3.connect('server/database/database.sqlite')
    conn.execute("ALTER TABLE Training ADD COLUMN questions TEXT DEFAULT '[]'")
    conn.commit()
    conn.close()
    print("DB migration applied")
except Exception as e:
    print("DB migration skip/error:", e)

# 2. Files to rewrite
files = {
    'server/database/db.ts': '''import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const dbPromise = open({
  filename: path.join(__dirname, 'database.sqlite'),
  driver: sqlite3.Database
});

export const initDb = async () => {
  const db = await dbPromise;
  await db.exec(`
    CREATE TABLE IF NOT EXISTS Training (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      description TEXT,
      trainer TEXT NOT NULL,
      location TEXT NOT NULL,
      date TEXT NOT NULL,
      qrCode TEXT,
      questions TEXT DEFAULT '[]'
    );

    CREATE TABLE IF NOT EXISTS Questions (
      id TEXT PRIMARY KEY,
      label TEXT NOT NULL,
      isActive INTEGER DEFAULT 1,
      orderIndex INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS Responses (
      id TEXT PRIMARY KEY,
      trainingId TEXT NOT NULL,
      employeeId TEXT NOT NULL,
      fullName TEXT NOT NULL,
      department TEXT NOT NULL,
      answers TEXT NOT NULL,
      comment TEXT,
      submittedAt TEXT NOT NULL,
      FOREIGN KEY(trainingId) REFERENCES Training(id)
    );
  `);
  return db;
};

export default dbPromise;
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
  const { title, description, trainer, location, date, origin } = req.body;
  const db = await dbPromise;
  const id = crypto.randomUUID();
  const qrCode = `${origin || 'http://localhost:5173'}/assessment/${id}`;
  
  // Fetch global active questions to snapshot them for this training
  const globalQuestions = await db.all('SELECT * FROM Questions WHERE isActive = 1 ORDER BY orderIndex ASC');
  const questionsJson = JSON.stringify(globalQuestions);
  
  await db.run(
    'INSERT INTO Training (id, title, description, trainer, location, date, qrCode, questions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
    [id, title, description, trainer, location, date, qrCode, questionsJson]
  );
  res.json({ success: true, id });
});

router.put('/:id', async (req, res) => {
  const { title, description, trainer, location, date, questions } = req.body;
  const db = await dbPromise;
  
  // questions is expected to be an array from frontend
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
''',

    'src/types/index.ts': '''export interface Training {
  id: string;
  title: string;
  description?: string;
  trainer: string;
  location: string;
  date: string;
  qrCode?: string;
  questions?: string; // JSON string of Question[]
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

export const updateTraining = async (id: string, data: any) => {
  const res = await fetch(`${API_URL}/trainings/${id}`, {
    method: 'PUT',
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

    'src/pages/admin/EditTraining.tsx': '''import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { fetchTraining, updateTraining } from '../../utils/api';
import { Training, Question } from '../../types';
import { Plus, Trash2, ArrowLeft } from 'lucide-react';

export default function EditTraining() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [training, setTraining] = useState<Training | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);
  const [newLabel, setNewLabel] = useState('');

  useEffect(() => {
    if (id) {
      fetchTraining(id).then(data => {
        setTraining(data);
        if (data.questions) {
          try {
            setQuestions(JSON.parse(data.questions));
          } catch (e) {
            // ignore
          }
        }
      }).catch(console.error);
    }
  }, [id]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!training) return;
    setLoading(true);
    
    const formData = new FormData(e.currentTarget);
    const data = {
      title: formData.get('title'),
      description: formData.get('description'),
      trainer: formData.get('trainer'),
      location: formData.get('location'),
      date: formData.get('date'),
      questions: questions
    };

    try {
      await updateTraining(training.id, data);
      navigate(`/admin/trainings/${training.id}`);
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

  if (!training) return <div className="text-center py-12">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center mb-6">
        <Link to={`/admin/trainings/${training.id}`} className="mr-4 text-gray-400 hover:text-gray-600">
          <ArrowLeft className="h-6 w-6" />
        </Link>
        <h2 className="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
          Edit Training: {training.title}
        </h2>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <h3 className="text-lg font-medium text-gray-900 border-b pb-2">Training Details</h3>
          
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700">Training Title</label>
            <input defaultValue={training.title} required type="text" name="title" id="title" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
          </div>

          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700">Description</label>
            <textarea defaultValue={training.description} name="description" id="description" rows={3} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm"></textarea>
          </div>

          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="trainer" className="block text-sm font-medium text-gray-700">Trainer Name</label>
              <input defaultValue={training.trainer} required type="text" name="trainer" id="trainer" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>

            <div>
              <label htmlFor="location" className="block text-sm font-medium text-gray-700">Location / Room</label>
              <input defaultValue={training.location} required type="text" name="location" id="location" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
            
            <div>
              <label htmlFor="date" className="block text-sm font-medium text-gray-700">Date</label>
              <input defaultValue={training.date} required type="date" name="date" id="date" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
          </div>

          <div className="mt-8">
            <h3 className="text-lg font-medium text-gray-900 border-b pb-2 mb-4">Specific Questions for this Training</h3>
            <p className="text-sm text-gray-500 mb-4">These questions are isolated to this specific session. Changing them here will not affect the Global default questions.</p>
            
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
              onClick={() => navigate(`/admin/trainings/${training.id}`)}
              className="bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="ml-3 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue"
            >
              {loading ? 'Saving...' : 'Save Changes'}
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
import { Download, ArrowLeft, Edit } from 'lucide-react';
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
        <div className="flex space-x-3">
          <Link
            to={`/admin/trainings/${id}/edit`}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Edit className="-ml-1 mr-2 h-5 w-5 text-gray-400" />
            Edit Settings
          </Link>
          <a
            href={`${API_URL}/trainings/${id}/export`}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
          >
            <Download className="-ml-1 mr-2 h-5 w-5" />
            Export to Excel
          </a>
        </div>
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
                        <p className="text-sm font-medium text-brand-blue">{res.fullName} ({res.employeeId})</p>
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
                className="text-brand-blue text-sm hover:underline break-all text-center"
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

    'src/pages/employee/AssessmentForm.tsx': '''import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchTraining, submitAssessment } from '../../utils/api';
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
      fetchTraining(id).then(data => {
        setTraining(data);
        if (data.questions) {
            try {
                // Parse questions from training JSON string
                const qs: Question[] = JSON.parse(data.questions);
                setQuestions(qs.filter(q => q.isActive === 1));
            } catch (e) {
                console.error(e);
            }
        }
      }).catch(() => setError('Training session not found.'));
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
      id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(),
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
      <div className="px-4 py-5 sm:px-6 bg-brand-blue text-white">
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
              <input required type="text" name="employeeId" id="employeeId" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-gray-700">Full Name *</label>
              <input required type="text" name="fullName" id="fullName" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="department" className="block text-sm font-medium text-gray-700">Department *</label>
              <input required type="text" name="department" id="department" className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm" />
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
                        <input required type="radio" name={q.id} value={rating} className="h-4 w-4 text-brand-blue border-gray-300 focus:ring-brand-blue" />
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
            <textarea name="comment" id="comment" rows={4} className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:ring-brand-blue focus:border-brand-blue sm:text-sm"></textarea>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={loading || questions.length === 0}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Submitting...' : 'Submit Assessment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
''',

    'src/App.tsx': '''import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import AdminDashboard from './pages/admin/AdminDashboard';
import CreateTraining from './pages/admin/CreateTraining';
import EditTraining from './pages/admin/EditTraining';
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
          <Route path="admin/trainings/:id/edit" element={<EditTraining />} />
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
}

for filepath, content in files.items():
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print('Updated files explicitly')

# Global Find and Replace for leftover generic terms
import glob
for filename in glob.iglob('**/*.*', recursive=True):
    if 'node_modules' in filename or '.git' in filename or '.sqlite' in filename or 'dist' in filename:
        continue
    if filename.endswith(('.ts', '.tsx', '.js', '.css', '.html')):
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = content.replace('microsoft-blue', 'brand-blue') \
                             .replace('microsoft-dark', 'brand-dark') \
                             .replace('microsoft-gray', 'brand-gray') \
                             .replace('Microsoft Onsite', 'Onsite') \
                             .replace('Microsoft', '')
                             
        if new_content != content:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'Replaced terminology in {filename}')
