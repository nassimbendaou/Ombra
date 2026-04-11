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
export const sendChat = (message, sessionId, forceProvider, whiteCardMode, agentId) =>
  fetchAPI('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId, force_provider: forceProvider, white_card_mode: whiteCardMode, agent_id: agentId }),
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

// Goal Planning
export const planGoal = (goal, context) =>
  fetchAPI('/goals/plan', { method: 'POST', body: JSON.stringify({ goal, context }) });
export const executeTaskStep = (taskId) =>
  fetchAPI(`/tasks/${taskId}/execute`, { method: 'POST' });

// Settings
export const getSettings = () => fetchAPI('/settings');
export const updateSettings = (settings) =>
  fetchAPI('/settings', { method: 'PUT', body: JSON.stringify(settings) });

// Terminal
export const executeTerminal = (command, timeout = 30) =>
  fetchAPI('/tools/terminal', { method: 'POST', body: JSON.stringify({ command, timeout }) });

// Filesystem
export const fsRead = (path) =>
  fetchAPI('/tools/fs/read', { method: 'POST', body: JSON.stringify({ path }) });
export const fsWrite = (path, content) =>
  fetchAPI('/tools/fs/write', { method: 'POST', body: JSON.stringify({ path, content }) });
export const fsList = (path) =>
  fetchAPI('/tools/fs/list', { method: 'POST', body: JSON.stringify({ path }) });

// Memories
export const getMemories = (type, limit = 50) =>
  fetchAPI(`/memories?${type ? `mem_type=${type}&` : ''}limit=${limit}`);
export const deleteMemory = (memoryId) =>
  fetchAPI(`/memories/${memoryId}`, { method: 'DELETE' });
export const clearMemories = () =>
  fetchAPI('/memories', { method: 'DELETE' });
export const pinMemory = (memoryId, pinned = true) =>
  fetchAPI(`/memories/${memoryId}/pin?pinned=${pinned}`, { method: 'PUT' });
export const runMemoryDecay = () =>
  fetchAPI('/memories/decay', { method: 'POST' });

// White Card
export const getWhiteCardSuggestions = () => fetchAPI('/white-card/suggestions');

// Agents
export const getAgents = () => fetchAPI('/agents');
export const createAgent = (agent) =>
  fetchAPI('/agents', { method: 'POST', body: JSON.stringify(agent) });
export const updateAgent = (agentId, agent) =>
  fetchAPI(`/agents/${agentId}`, { method: 'PUT', body: JSON.stringify(agent) });
export const deleteAgent = (agentId) =>
  fetchAPI(`/agents/${agentId}`, { method: 'DELETE' });
export const runAgent = (agentId, message) =>
  fetchAPI(`/agents/${agentId}/run`, { method: 'POST', body: JSON.stringify({ message }) });

// Feedback
export const submitFeedback = (sessionId, messageIndex, feedback, comment) =>
  fetchAPI('/feedback', { method: 'POST', body: JSON.stringify({ session_id: sessionId, message_index: messageIndex, feedback, comment }) });

// Learning / Self-Improving
export const getLearningMetrics = () => fetchAPI('/learning/metrics');
export const getLearningChanges = () => fetchAPI('/learning/changes');

// Ollama Model Manager
export const getOllamaModels = () => fetchAPI('/ollama/models');
export const getModelRecommendations = () => fetchAPI('/ollama/recommendations');
export const pullOllamaModel = (modelName) =>
  fetchAPI('/ollama/pull', { method: 'POST', body: JSON.stringify({ model_name: modelName }) });
export const deleteOllamaModel = (modelName) =>
  fetchAPI(`/ollama/models/${modelName}`, { method: 'DELETE' });

// K1 Prompts
export const getK1Prompts = () => fetchAPI('/k1/prompts');
export const getK1Distillations = (limit = 20) => fetchAPI(`/k1/distillations?limit=${limit}`);

// Telegram
export const testTelegram = () => fetchAPI('/telegram/test', { method: 'POST' });
export const sendTelegramMessage = (chatId, message) =>
  fetchAPI('/telegram/send', { method: 'POST', body: JSON.stringify({ chat_id: chatId, message }) });
export const sendTelegramSummary = () => fetchAPI('/telegram/send-summary', { method: 'POST' });

// Intuition
export const getIntentPrediction = () => fetchAPI('/intuition/prediction');
export const getIntuitionSuggestions = () => fetchAPI('/intuition/suggestions');
