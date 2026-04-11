import React, { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, MessageSquare, Shield, Activity, Settings,
  ChevronLeft, ChevronRight, Zap, Menu, X, Bot, Cpu, Brain
} from 'lucide-react';
import { Button } from './ui/button';
import { Separator } from './ui/separator';
import { getPermissions } from '../lib/api';
import StatusIndicator from './StatusIndicator';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/chat', icon: MessageSquare, label: 'Chat' },
  { path: '/agents', icon: Bot, label: 'Agents' },
  { path: '/models', icon: Cpu, label: 'Models' },
  { path: '/memories', icon: Brain, label: 'Memories' },
  { path: '/permissions', icon: Shield, label: 'Permissions' },
  { path: '/activity', icon: Activity, label: 'Activity' },
  { path: '/settings', icon: Settings, label: 'Settings' },
];

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [onboarded, setOnboarded] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    getPermissions().then(p => {
      if (!p.onboarded) {
        setOnboarded(false);
        navigate('/onboarding');
      }
    }).catch(() => {});
  }, [navigate]);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  if (!onboarded && location.pathname !== '/onboarding') return null;

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Desktop Sidebar */}
      <motion.aside
        className="hidden md:flex flex-col border-r border-border/60 bg-card/80 backdrop-blur"
        animate={{ width: collapsed ? 72 : 260 }}
        transition={{ duration: 0.2 }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-16 border-b border-border/60">
          <div className="w-9 h-9 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
            <Zap className="w-5 h-5 text-primary" />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                className="overflow-hidden"
              >
                <span className="text-lg font-semibold tracking-tight whitespace-nowrap">Ombra</span>
                <span className="block text-[10px] text-muted-foreground font-mono-ombra whitespace-nowrap">Autonomous AI Agent</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-2 space-y-1">
          {navItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase()}`}
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-200
                ${isActive
                  ? 'bg-secondary/70 border border-border/60 text-foreground'
                  : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
                }
              `}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: 'auto' }}
                    exit={{ opacity: 0, width: 0 }}
                    className="whitespace-nowrap overflow-hidden"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </NavLink>
          ))}
        </nav>

        {/* Status */}
        <div className="px-3 py-3 border-t border-border/60">
          <StatusIndicator compact={collapsed} />
        </div>

        {/* Collapse toggle */}
        <div className="px-3 py-2 border-t border-border/60">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center justify-center"
            data-testid="sidebar-collapse-toggle"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </Button>
        </div>
      </motion.aside>

      {/* Mobile Header + Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="md:hidden flex items-center gap-3 h-14 px-4 border-b border-border/60 bg-card/80 backdrop-blur">
          <Button variant="ghost" size="icon" onClick={() => setMobileOpen(!mobileOpen)} data-testid="mobile-menu-toggle">
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary" />
            <span className="font-semibold">Ombra</span>
          </div>
        </header>

        {/* Mobile Nav Overlay */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="md:hidden absolute inset-x-0 top-14 z-50 bg-card border-b border-border/60 p-4 space-y-1"
            >
              {navItems.map(item => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) => `
                    flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                    ${isActive ? 'bg-secondary/70 text-foreground' : 'text-muted-foreground hover:bg-secondary/50'}
                  `}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
