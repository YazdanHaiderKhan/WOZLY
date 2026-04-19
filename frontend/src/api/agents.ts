import { apiClient } from './client'

export const agentsApi = {
  // ── Profile Agent ──────────────────────────────────────────────────────────
  startProfile: () =>
    apiClient.post('/agent/profile/start').then((r) => r.data),

  respondProfile: (sessionId: string, message: string) =>
    apiClient.post('/agent/profile/respond', { session_id: sessionId, message }).then((r) => r.data),

  confirmProfile: (data: { domain: string, goal: string, duration_weeks: number, knowledge_level: string, learning_style: string, hours_per_day: number }) =>
    apiClient.post('/agent/profile/confirm', data).then((r) => r.data),

  resetProfile: () =>
    apiClient.delete('/agent/profile/reset').then((r) => r.data),

  // ── Tutor Agent ────────────────────────────────────────────────────────────
  tutorChat: (userId: string, topicId: string, message: string, history: object[]) =>
    apiClient.post('/agent/tutor/chat', { user_id: userId, topic_id: topicId, message, history }).then((r) => r.data),

  // SSE streaming URL (used with EventSource)
  tutorStreamUrl: () => `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/agent/tutor/chat/stream`,
}

export const roadmapApi = {
  getRoadmap: (userId: string) =>
    apiClient.get(`/roadmap/${userId}`).then((r) => r.data),

  generateRoadmap: (userId: string) =>
    apiClient.post('/roadmap/generate', { user_id: userId }).then((r) => r.data),
}

export const assessmentApi = {
  generateQuiz: (userId: string, weekNumber: number) =>
    apiClient.post('/assessment/generate', { user_id: userId, week_number: weekNumber }).then((r) => r.data),

  submitQuiz: (quizId: string, answers: { question_id: string; answer: string }[]) =>
    apiClient.post('/assessment/submit', { quiz_id: quizId, answers }).then((r) => r.data),
}

export const userApi = {
  getMe: () => apiClient.get('/user/me').then((r) => r.data),
  deleteAccount: (userId: string) => apiClient.delete(`/user/${userId}`),
}
