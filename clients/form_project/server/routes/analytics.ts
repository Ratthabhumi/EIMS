import { Router } from 'express';
import dbPromise from '../database/db.js';

const router = Router();

router.get('/', async (_req, res) => {
  try {
    const db = await dbPromise;
    
    // Total projects
    const { totalProjects } = await db.get('SELECT COUNT(*) as totalProjects FROM Training');
    
    // Total responses
    const { totalResponses } = await db.get('SELECT COUNT(*) as totalResponses FROM Responses');

    // To get the average score across ALL responses, we must parse the answers JSON.
    // SQLite JSON function can help, but for simplicity and compatibility, we'll fetch them.
    const responses = await db.all('SELECT answers FROM Responses');
    
    let totalScore = 0;
    let answerCount = 0;
    
    responses.forEach(r => {
      try {
        const parsedAnswers = JSON.parse(r.answers);
        parsedAnswers.forEach((ans: any) => {
          totalScore += Number(ans.score);
          answerCount++;
        });
      } catch (e) {
        // Ignore invalid JSON
      }
    });

    const averageScore = answerCount > 0 ? Number((totalScore / answerCount).toFixed(1)) : 0;

    res.json({
      totalProjects,
      totalResponses,
      averageScore
    });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

export default router;
