import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function run() {
  const db = await open({
    filename: path.join(__dirname, 'server', 'database', 'database.sqlite'),
    driver: sqlite3.Database
  });

  await db.exec('DELETE FROM Questions');
  console.log('Cleared Questions table');
}
run();
