import { Router } from 'express';
import dbPromise from '../database/db.js';

const router = Router();

router.get('/', async (_req, res) => {
  const db = await dbPromise;
  const questions = await db.all('SELECT * FROM Questions ORDER BY orderIndex ASC');
  res.json(questions);
});

router.post('/', async (req, res) => {
  const { id, label, isActive, orderIndex, category } = req.body;
  const db = await dbPromise;
  await db.run(
    'INSERT INTO Questions (id, label, isActive, orderIndex, category) VALUES (?, ?, ?, ?, ?)',
    [id, label, isActive, orderIndex, category || 'General']
  );
  res.json({ success: true, id });
});

router.put('/:id', async (req, res) => {
  const { label, isActive, orderIndex, category } = req.body;
  const db = await dbPromise;
  await db.run(
    'UPDATE Questions SET label = ?, isActive = ?, orderIndex = ?, category = ? WHERE id = ?',
    [label, isActive, orderIndex, category || 'General', req.params.id]
  );
  res.json({ success: true });
});

router.delete('/:id', async (req, res) => {
  const db = await dbPromise;
  await db.run('DELETE FROM Questions WHERE id = ?', [req.params.id]);
  res.json({ success: true });
});

export default router;
