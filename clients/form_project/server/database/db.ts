import sqlite3 from 'sqlite3';
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
      orderIndex INTEGER DEFAULT 0,
      category TEXT DEFAULT 'General'
    );

    CREATE TABLE IF NOT EXISTS Responses (
      id TEXT PRIMARY KEY,
      trainingId TEXT NOT NULL,
      kelCaseId TEXT NOT NULL,
      fullName TEXT NOT NULL,
      department TEXT NOT NULL,
      position TEXT NOT NULL,
      answers TEXT NOT NULL,
      comment TEXT,
      submittedAt TEXT NOT NULL,
      FOREIGN KEY(trainingId) REFERENCES Training(id)
    );
  `);

  // Migrations
  const questionsTableInfo = await db.all("PRAGMA table_info(Questions)");
  if (!questionsTableInfo.find((col: any) => col.name === 'category')) {
    await db.exec("ALTER TABLE Questions ADD COLUMN category TEXT DEFAULT 'General'");
  }

  const responsesTableInfo = await db.all("PRAGMA table_info(Responses)");
  if (responsesTableInfo.find((col: any) => col.name === 'employeeId')) {
    await db.exec("ALTER TABLE Responses RENAME COLUMN employeeId TO kelCaseId");
  }
  if (!responsesTableInfo.find((col: any) => col.name === 'position')) {
    await db.exec("ALTER TABLE Responses ADD COLUMN position TEXT DEFAULT ''");
  }

  // Seed default questions if empty
  const qCount = await db.get("SELECT COUNT(*) as count FROM Questions");
  if (qCount.count === 0) {
    const defaultQuestions = [
      { id: 'q1', label: 'ความรวดเร็วในการแก้ไขปัญหา (Resolution Time & Efficiency)', category: 'Support', orderIndex: 1 },
      { id: 'q2', label: 'ความเป็นมืออาชีพและการให้บริการ (Professionalism & Service Quality)', category: 'Support', orderIndex: 2 },
      { id: 'q3', label: 'การแก้ไขปัญหาได้สำเร็จและครบถ้วน (Resolution Quality)', category: 'Support', orderIndex: 3 },
      { id: 'q4', label: 'ความตรงต่อเวลาในการส่งมอบงาน (Punctuality)', category: 'Implement', orderIndex: 4 },
      { id: 'q5', label: 'คุณภาพของการติดตั้งระบบ (Implementation Quality)', category: 'Implement', orderIndex: 5 },
      { id: 'q6', label: 'การถ่ายทอดความรู้และการสอนใช้งาน (Knowledge Transfer)', category: 'Implement', orderIndex: 6 },
      { id: 'q7', label: 'ความพึงพอใจโดยรวมต่อการให้บริการ (Overall Satisfaction)', category: 'General', orderIndex: 7 }
    ];
    for (const q of defaultQuestions) {
      await db.run(
        'INSERT INTO Questions (id, label, isActive, orderIndex, category) VALUES (?, ?, 1, ?, ?)',
        [q.id, q.label, q.orderIndex, q.category]
      );
    }
  }

  return db;
};

export default dbPromise;
