import { Router } from 'express';
import dbPromise from '../database/db.js';
import { validate } from '../middleware/validate.js';
import { assessmentResponseSchema, updateAssessmentResponseSchema } from '../schemas/index.js';

const router = Router();

router.post('/', validate(assessmentResponseSchema), async (req, res) => {
  const { id, trainingId, kelCaseId, fullName, department, position, answers, comment, submittedAt } = req.body;
  const db = await dbPromise;
  
  try {
    await db.run(
      'INSERT INTO Responses (id, trainingId, kelCaseId, fullName, department, position, answers, comment, submittedAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
      [id, trainingId, kelCaseId, fullName, department, position, JSON.stringify(answers), comment, submittedAt]
    );
    res.json({ success: true });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

router.put('/:id', validate(updateAssessmentResponseSchema), async (req, res) => {
  const { kelCaseId, fullName, department, position, comment } = req.body;
  const db = await dbPromise;
  
  try {
    await db.run(
      'UPDATE Responses SET kelCaseId = ?, fullName = ?, department = ?, position = ?, comment = ? WHERE id = ?',
      [kelCaseId, fullName, department, position, comment, req.params.id]
    );
    res.json({ success: true });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

router.delete('/:id', async (req, res) => {
  const db = await dbPromise;
  
  try {
    await db.run('DELETE FROM Responses WHERE id = ?', [req.params.id]);
    res.json({ success: true });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
