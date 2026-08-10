import os

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
      qrCode TEXT
    );

    CREATE TABLE IF NOT EXISTS Responses (
      id TEXT PRIMARY KEY,
      trainingId TEXT NOT NULL,
      employeeId TEXT NOT NULL,
      fullName TEXT NOT NULL,
      department TEXT NOT NULL,
      q1 INTEGER NOT NULL,
      q2 INTEGER NOT NULL,
      q3 INTEGER NOT NULL,
      q4 INTEGER NOT NULL,
      q5 INTEGER NOT NULL,
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

const router = Router();

router.get('/', async (req, res) => {
  const db = await dbPromise;
  const trainings = await db.all('SELECT * FROM Training ORDER BY date DESC');
  res.json(trainings);
});

router.post('/', async (req, res) => {
  const { id, title, description, trainer, location, date } = req.body;
  const db = await dbPromise;
  const qrCode = `http://localhost:5173/assessment/${id}`;
  
  await db.run(
    'INSERT INTO Training (id, title, description, trainer, location, date, qrCode) VALUES (?, ?, ?, ?, ?, ?, ?)',
    [id, title, description, trainer, location, date, qrCode]
  );
  res.json({ success: true, id });
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
  
  const data = responses.map(r => ({
    'Employee ID': r.employeeId,
    'Name': r.fullName,
    'Department': r.department,
    'Training': training.title,
    'Trainer': training.trainer,
    'Date': training.date,
    'Q1 (Content)': r.q1,
    'Q2 (Trainer)': r.q2,
    'Q3 (Knowledge)': r.q3,
    'Q4 (Materials)': r.q4,
    'Q5 (Overall)': r.q5,
    'Average Score': ((r.q1 + r.q2 + r.q3 + r.q4 + r.q5) / 5).toFixed(2),
    'Comment': r.comment || '',
    'Submitted Time': new Date(r.submittedAt).toLocaleString()
  }));

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

    'server/routes/assessments.ts': '''import { Router } from 'express';
import dbPromise from '../database/db.js';

const router = Router();

router.post('/', async (req, res) => {
  const { id, trainingId, employeeId, fullName, department, q1, q2, q3, q4, q5, comment, submittedAt } = req.body;
  const db = await dbPromise;
  
  try {
    await db.run(
      'INSERT INTO Responses (id, trainingId, employeeId, fullName, department, q1, q2, q3, q4, q5, comment, submittedAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
      [id, trainingId, employeeId, fullName, department, q1, q2, q3, q4, q5, comment, submittedAt]
    );
    res.json({ success: true });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
''',

    'server/index.ts': '''import express from 'express';
import cors from 'cors';
import { initDb } from './database/db.js';
import trainingsRouter from './routes/trainings.js';
import assessmentsRouter from './routes/assessments.js';

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

app.use('/api/trainings', trainingsRouter);
app.use('/api/assessments', assessmentsRouter);

initDb().then(() => {
  console.log('SQLite database initialized.');
  app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
  });
}).catch(err => {
  console.error('Failed to initialize database', err);
});
'''
}

for filepath, content in files.items():
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print('Backend files created')
