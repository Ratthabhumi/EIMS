import { Router, Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';
import rateLimit from 'express-rate-limit';
import 'dotenv/config';

const router = Router();

// Credentials จาก environment variables (ไม่ hard-code ใน code)
const ADMIN_USERNAME = process.env.ADMIN_USERNAME || 'admin';
const ADMIN_PASSWORD_HASH = process.env.ADMIN_PASSWORD
  ? bcrypt.hashSync(process.env.ADMIN_PASSWORD, 10)
  : bcrypt.hashSync('P@ssw0rd', 10);
const JWT_SECRET = process.env.JWT_SECRET || 'fallback-secret-change-this';

// Rate Limiting: ให้ login ได้สูงสุด 10 ครั้งต่อ 15 นาที
export const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  message: { error: 'Too many login attempts. Please try again in 15 minutes.' },
  standardHeaders: true,
  legacyHeaders: false,
});

// Middleware ตรวจสอบ JWT Token
export const authenticateToken = (req: Request, res: Response, next: NextFunction) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Access denied. No token provided.' });
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    (req as any).user = decoded;
    next();
  } catch (err) {
    return res.status(403).json({ error: 'Invalid or expired token.' });
  }
};

// POST /api/auth/login
router.post('/login', loginLimiter, async (req: Request, res: Response) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required.' });
  }

  // ตรวจสอบ username ก่อน (ป้องกัน timing attack บางส่วน)
  if (username !== ADMIN_USERNAME) {
    return res.status(401).json({ error: 'Invalid username or password.' });
  }

  // ตรวจสอบ password ด้วย bcrypt (ปลอดภัยกว่า plaintext compare)
  const isPasswordValid = await bcrypt.compare(password, ADMIN_PASSWORD_HASH);
  if (!isPasswordValid) {
    return res.status(401).json({ error: 'Invalid username or password.' });
  }

  const token = jwt.sign(
    { username, role: 'admin' },
    JWT_SECRET,
    { expiresIn: '8h' }
  );

  res.json({ success: true, token, username });
});

// POST /api/auth/verify
router.post('/verify', (req: Request, res: Response) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ valid: false });
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    res.json({ valid: true, user: decoded });
  } catch {
    res.status(403).json({ valid: false });
  }
});

export default router;
