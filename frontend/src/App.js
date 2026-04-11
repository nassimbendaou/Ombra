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
            <Route path="/permissions" element={<Permissions />} />
            <Route path="/activity" element={<ActivityTimeline />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        <Toaster position="bottom-right" theme="dark" />
      </Router>
    </div>
  );
}

export default App;
