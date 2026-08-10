import { Router } from 'express';
import dbPromise from '../database/db.js';
import * as xlsx from 'xlsx';
import crypto from 'crypto';
import { validate } from '../middleware/validate.js';
import { trainingSchema } from '../schemas/index.js';

const router = Router();

router.get('/', async (_req, res) => {
  const db = await dbPromise;
  const trainings = await db.all('SELECT * FROM Training ORDER BY date DESC');
  res.json(trainings);
});

router.post('/', validate(trainingSchema), async (req, res) => {
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

router.put('/:id', validate(trainingSchema), async (req, res) => {
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
      'Kel Case ID': r.kelCaseId,
      'Name': r.fullName,
      'Department': r.department,
      'Position': r.position,
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

router.delete('/:id', async (req, res) => {
  const db = await dbPromise;
  await db.run('DELETE FROM Responses WHERE trainingId = ?', [req.params.id]);
  await db.run('DELETE FROM Training WHERE id = ?', [req.params.id]);
  res.json({ success: true });
});

export default router;
