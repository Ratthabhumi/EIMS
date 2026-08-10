export const API_URL = '/api';

// ดึง JWT token จาก localStorage แนบไปกับ request ที่ต้องการ Auth
const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

// Fetch สำหรับ Admin routes (ต้องการ JWT)
const apiFetch = async (endpoint: string, options: RequestInit = {}) => {
  const headers = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
    ...options.headers,
  };

  const res = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401 || res.status === 403) {
    // Token หมดอายุหรือไม่ถูกต้อง → logout และ redirect ไป login
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
};

// Fetch สำหรับ Public routes (ไม่ต้องการ Auth เช่น assessment form)
const publicFetch = async (endpoint: string, options: RequestInit = {}) => {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const res = await fetch(`${API_URL}${endpoint}`, { ...options, headers });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
};

// --- Admin Routes (Protected) ---
export const fetchTrainings = () => apiFetch('/trainings');
export const fetchTraining = (id: string) => apiFetch(`/trainings/${id}`);
export const createTraining = (data: any) =>
  apiFetch('/trainings', { method: 'POST', body: JSON.stringify(data) });
export const updateTraining = (id: string, data: any) =>
  apiFetch(`/trainings/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteTraining = (id: string) =>
  apiFetch(`/trainings/${id}`, { method: 'DELETE' });
export const fetchResponses = (id: string) =>
  apiFetch(`/trainings/${id}/responses`);

export const fetchQuestions = () => apiFetch('/questions');
export const createQuestion = (data: any) =>
  apiFetch('/questions', { method: 'POST', body: JSON.stringify(data) });
export const updateQuestion = (id: string, data: any) =>
  apiFetch(`/questions/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteQuestion = (id: string) =>
  apiFetch(`/questions/${id}`, { method: 'DELETE' });

export const updateResponse = (id: string, data: any) =>
  apiFetch(`/assessments/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteResponse = (id: string) =>
  apiFetch(`/assessments/${id}`, { method: 'DELETE' });

export const fetchAnalytics = () => apiFetch('/analytics');

// --- Public Routes (No Auth required) ---
export const fetchTrainingPublic = (id: string) =>
  publicFetch(`/trainings/public/${id}`);
export const submitAssessment = (data: any) =>
  publicFetch('/assessments', { method: 'POST', body: JSON.stringify(data) });
