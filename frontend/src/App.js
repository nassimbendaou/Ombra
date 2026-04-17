import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/AppShell';
import Dashboard from './pages/Dashboard';
import Chat from './pages/Chat';
import Permissions from './pages/Permissions';
import ActivityTimeline from './pages/ActivityTimeline';
import Settings from './pages/Settings';
import Onboarding from './pages/Onboarding';
import Agents from './pages/Agents';
import ModelManager from './pages/ModelManager';
import MemoryManagement from './pages/MemoryManagement';
import Analytics from './pages/Analytics';
import Skills from './pages/Skills';
import EmailDrafts from './pages/EmailDrafts';
import BrainView from './pages/BrainView';
import McpManager from './pages/McpManager';
import CodebaseExplorer from './pages/CodebaseExplorer';
import GithubIntegration from './pages/GithubIntegration';
import PluginHooks from './pages/PluginHooks';
import ToolsLab from './pages/ToolsLab';
import Bastion from './pages/Bastion';
import SecurityCenter from './pages/SecurityCenter';
import { Toaster } from './components/ui/sonner';
import './App.css';

function App() {
  return (
    <div className="dark">
      <Router>
        <Routes>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route element={<AppShell />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/models" element={<ModelManager />} />
            <Route path="/memories" element={<MemoryManagement />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/brain" element={<BrainView />} />
            <Route path="/skills" element={<Skills />} />
            <Route path="/permissions" element={<Permissions />} />
            <Route path="/activity" element={<ActivityTimeline />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/drafts" element={<EmailDrafts />} />
            <Route path="/mcp" element={<McpManager />} />
            <Route path="/codebase" element={<CodebaseExplorer />} />
            <Route path="/github" element={<GithubIntegration />} />
            <Route path="/hooks" element={<PluginHooks />} />
            <Route path="/tools-lab" element={<ToolsLab />} />
            <Route path="/bastion" element={<Bastion />} />
            <Route path="/security" element={<SecurityCenter />} />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        <Toaster position="bottom-right" theme="dark" />
      </Router>
    </div>
  );
}

export default App;
