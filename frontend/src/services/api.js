const API_BASE_URL = 'http://localhost:8000';

export const api = {
  // קבלת רשימת הפרויקטים (לדף הנחיתה)
  async getProjects() {
    const res = await fetch(`${API_BASE_URL}/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  },

  // קבלת המשימה הבאה לתיוג
  async getNextMission(projectId) {
    const res = await fetch(`${API_BASE_URL}/next-mission/${projectId}`);
    if (!res.ok) throw new Error('Failed to fetch mission');
    return res.json();
  },

  // שליחת התיוג ושמירתו
  async submitLabel(data) {
    const res = await fetch(`${API_BASE_URL}/submit-label`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to submit label');
    return res.json();
  }
};
