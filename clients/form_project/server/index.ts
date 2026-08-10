import express from 'express';
import cors from 'cors';
import 'dotenv/config';
import { initDb } from './database/db.js';
import trainingsRouter from './routes/trainings.js';
import assessmentsRouter from './routes/assessments.js';
import questionsRouter from './routes/questions.js';
import analyticsRouter from './routes/analytics.js';
import authRouter, { authenticateToken } from './routes/auth.js';

const app = express();
const PORT = Number(process.env.PORT) || 3000;

app.use(cors());
app.use(express.json());

// Public routes (ไม่ต้อง login)
app.use('/api/auth', authRouter);
app.use('/api/assessments', assessmentsRouter);    // พนักงาน submit ได้เลย
app.use('/api/trainings/public', trainingsRouter); // public endpoint สำหรับพนักงาน fetch training

// Protected routes (ต้อง login ก่อน)
app.use('/api/trainings', authenticateToken, trainingsRouter);
app.use('/api/questions', authenticateToken, questionsRouter);
app.use('/api/analytics', authenticateToken, analyticsRouter);

initDb().then(() => {
  console.log('SQLite database initialized.');
  app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
  });
}).catch(err => {
  console.error('Failed to initialize database', err);
});
