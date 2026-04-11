const API_BASE = (process.env.REACT_APP_BACKEND_URL || '') + '/api';

async function fetchAPI(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error ${response.status}: ${error}`);
  }
  return response.json();
}

// Health
export const getHealth = () => fetchAPI('/health');

// Chat
export const sendChat = (message, sessionId, forceProvider, whiteCardMode) =>
  fetchAPI('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId, force_provider: forceProvider, white_card_mode: whiteCardMode }),
  });

export const getChatHistory = (sessionId) =>
  fetchAPI(`/chat/history${sessionId ? `?session_id=${sessionId}` : ''}`);

export const clearChatHistory = (sessionId) =>
  fetchAPI(`/chat/history${sessionId ? `?session_id=${sessionId}` : ''}`, { method: 'DELETE' });

// Dashboard
export const getDashboardSummary = () => fetchAPI('/dashboard/summary');
export const getSystemStatus = () => fetchAPI('/dashboard/status');

// Permissions
export const getPermissions = () => fetchAPI('/permissions');
export const updatePermissions = (perms) =>
  fetchAPI('/permissions', { method: 'PUT', body: JSON.stringify(perms) });
export const completeOnboarding = (perms) =>
  fetchAPI('/onboarding', { method: 'POST', body: JSON.stringify(perms) });

// Activity
export const getActivity = (type, limit = 50, offset = 0) =>
  fetchAPI(`/activity?${type && type !== 'all' ? `activity_type=${type}&` : ''}limit=${limit}&offset=${offset}`);
export const getActivitySummary = () => fetchAPI('/activity/summary');

// Tasks
export const getTasks = (status) =>
  fetchAPI(`/tasks${status ? `?status=${status}` : ''}`);
export const createTask = (title, description, priority) =>
  fetchAPI('/tasks', { method: 'POST', body: JSON.stringify({ title, description, priority }) });
export const updateTask = (taskId, status, result) =>
  fetchAPI(`/tasks/${taskId}?${status ? `status=${status}` : ''}${result ? `&result=${result}` : ''}`, { method: 'PUT' });
export const deleteTask = (taskId) =>
  fetchAPI(`/tasks/${taskId}`, { method: 'DELETE' });

// Settings
export const getSettings = () => fetchAPI('/settings');
export const updateSettings = (settings) =>
  fetchAPI('/settings', { method: 'PUT', body: JSON.stringify(settings) });

// Terminal
export const executeTerminal = (command, timeout = 30) =>
  fetchAPI('/tools/terminal', { method: 'POST', body: JSON.stringify({ command, timeout }) });

// Memories
export const getMemories = (type, limit = 50) =>
  fetchAPI(`/memories?${type ? `mem_type=${type}&` : ''}limit=${limit}`);
export const deleteMemory = (memoryId) =>
  fetchAPI(`/memories/${memoryId}`, { method: 'DELETE' });
export const clearMemories = () =>
  fetchAPI('/memories', { method: 'DELETE' });

// White Card
export const getWhiteCardSuggestions = () => fetchAPI('/white-card/suggestions');
