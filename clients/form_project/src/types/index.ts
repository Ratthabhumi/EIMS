export interface Training {
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
  category?: string;
}

export interface Answer {
  questionId: string;
  label: string;
  score: number;
}

export interface Response {
  id: string;
  trainingId: string;
  kelCaseId: string;
  fullName: string;
  department: string;
  position: string;
  answers: string; // JSON string of Answer[]
  comment?: string;
  submittedAt: string;
}
