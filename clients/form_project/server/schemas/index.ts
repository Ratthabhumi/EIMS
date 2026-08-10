import { z } from 'zod';

export const questionSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1, 'Question label is required'),
  isActive: z.number().int().min(0).max(1),
  orderIndex: z.number().int().min(0),
  category: z.string().optional(),
});

export const trainingSchema = z.object({
  id: z.string().optional(),
  title: z.string().min(1, 'Title is required'),
  description: z.string().optional(),
  trainer: z.string().min(1, 'Trainer is required'),
  location: z.string().min(1, 'Location is required'),
  date: z.string().min(1, 'Date is required'),
  qrCode: z.string().optional(),
  questions: z.any().optional(), // allow any type (array or string) before JSON stringification
});

export const answerSchema = z.object({
  questionId: z.string().min(1),
  label: z.string().min(1),
  score: z.number().int().min(1).max(5),
});

export const assessmentResponseSchema = z.object({
  id: z.string().min(1),
  trainingId: z.string().min(1),
  kelCaseId: z.string().min(1, 'KEL Case ID is required'),
  fullName: z.string().min(1, 'Full Name is required'),
  department: z.string().min(1, 'Department is required'),
  position: z.string().min(1, 'Position is required'),
  answers: z.array(answerSchema).min(1, 'At least one answer is required'),
  comment: z.string().optional(),
  submittedAt: z.string().optional(),
});

export const updateAssessmentResponseSchema = z.object({
  kelCaseId: z.string().min(1, 'KEL Case ID is required'),
  fullName: z.string().min(1, 'Full Name is required'),
  department: z.string().min(1, 'Department is required'),
  position: z.string().min(1, 'Position is required'),
  comment: z.string().optional(),
});
