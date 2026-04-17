import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import {
  Shield, ShieldAlert, ShieldCheck, ShieldX, Scan, Globe, Server, Lock,
  Wifi, AlertTriangle, Activity, Eye, FileSearch, RefreshCw, Play,
  ChevronRight, ExternalLink, Terminal, Bug, Network, Search, MapPin,
  Route, Radio, Clock, Code, Layers, Database
} from 'lucide-react';
import {
  securityPortScan, securitySslCheck, securitySystemAudit, securityLogAnalysis,
  securityDnsCheck, securityHttpHeaders, securityIpLookup, securityFullScan,
  securityDashboard, securityHistory, securityWhois, securitySubdomains,
  securityTechFingerprint, securityTraceroute, securityBannerGrab, securityWayback
} from '../lib/api';

const SEVERITY_COLORS = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
};

const GRADE_COLORS = {
  A: 'text-emerald-400', B: 'text-blue-400', C: 'text-yellow-400',
  D: 'text-orange-400', F: 'text-red-400',
};

function SeverityBadge({ severity }) {
  return (
    <Badge variant="outline" className={`text-[10px] uppercase tracking-wider ${SEVERITY_COLORS[severity] || SEVERITY_COLORS.info}`}>
      {severity}
    </Badge>
  );
}

function ScoreRing({ score, grade, size = 120 }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = ((score || 0) / 100) * circumference;
  const color = (score || 0) >= 90 ? '#34d399' : (score || 0) >= 75 ? '#60a5fa' : (score || 0) >= 60 ? '#fbbf24' : (score || 0) >= 40 ? '#fb923c' : '#f87171';

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circumference} strokeDashoffset={circumference - progress}
          strokeLinecap="round" className="transition-all duration-1000" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-2xl font-bold ${GRADE_COLORS[grade] || 'text-zinc-400'}`}>{grade || '—'}</span>
        <span className="text-xs text-muted-foreground">{score ?? '—'}/100</span>
      </div>
    </div>
  );
}

function ScanButton({ onClick, loading, icon: Icon, label }) {
  return (
    <Button size="sm" variant="outline" onClick={onClick} disabled={loading}
      className="gap-2 border-border/60 hover:border-primary/50 hover:bg-primary/5 transition-all">
      {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />}
      {label}
    </Button>
  );
}

export default function SecurityCenter() {
  const [dashboard, setDashboard] = useState(null);
  const [portScan, setPortScan] = useState(null);
  const [sslResult, setSslResult] = useState(null);
  const [auditResult, setAuditResult] = useState(null);
  const [logResult, setLogResult] = useState(null);
  const [headerResult, setHeaderResult] = useState(null);
  const [dnsResult, setDnsResult] = useState(null);
  const [ipResult, setIpResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState({});
  const [scanHost, setScanHost] = useState('localhost');
  const [lookupIp, setLookupIp] = useState('');
  const [dnsTarget, setDnsTarget] = useState('');
  const [headerUrl, setHeaderUrl] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  // External recon state
  const [whoisTarget, setWhoisTarget] = useState('');
  const [whoisResult, setWhoisResult] = useState(null);
  const [subdomainTarget, setSubdomainTarget] = useState('');
  const [subdomainResult, setSubdomainResult] = useState(null);
  const [techUrl, setTechUrl] = useState('');
  const [techResult, setTechResult] = useState(null);
  const [traceHost, setTraceHost] = useState('');
  const [traceResult, setTraceResult] = useState(null);
  const [bannerHost, setBannerHost] = useState('');
  const [bannerResult, setBannerResult] = useState(null);
  const [waybackUrl, setWaybackUrl] = useState('');
  const [waybackResult, setWaybackResult] = useState(null);

  const setLoadingState = (key, val) => setLoading(prev => ({ ...prev, [key]: val }));

  const loadDashboard = useCallback(async () => {
    try {
      const [dash, hist] = await Promise.all([
        securityDashboard().catch(() => null),
        securityHistory(null, 10).catch(() => ({ scans: [] }))
      ]);
      if (dash) setDashboard(dash);
      setHistory(hist.scans || []);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  const runPortScan = async () => {
    setLoadingState('port', true);
    try { setPortScan(await securityPortScan(scanHost)); } catch (e) { console.error(e); }
    setLoadingState('port', false);
  };

  const runSslCheck = async () => {
    setLoadingState('ssl', true);
    try { setSslResult(await securitySslCheck(scanHost)); } catch (e) { console.error(e); }
    setLoadingState('ssl', false);
  };

  const runAudit = async () => {
    setLoadingState('audit', true);
    try { setAuditResult(await securitySystemAudit()); } catch (e) { console.error(e); }
    setLoadingState('audit', false);
  };

  const runLogAnalysis = async () => {
    setLoadingState('logs', true);
    try { setLogResult(await securityLogAnalysis()); } catch (e) { console.error(e); }
    setLoadingState('logs', false);
  };

  const runHeaderCheck = async () => {
    if (!headerUrl) return;
    setLoadingState('headers', true);
    try { setHeaderResult(await securityHttpHeaders(headerUrl)); } catch (e) { console.error(e); }
    setLoadingState('headers', false);
  };

  const runDnsCheck = async () => {
    if (!dnsTarget) return;
    setLoadingState('dns', true);
    try { setDnsResult(await securityDnsCheck(dnsTarget)); } catch (e) { console.error(e); }
    setLoadingState('dns', false);
  };

  const runIpLookup = async () => {
    if (!lookupIp) return;
    setLoadingState('ip', true);
    try { setIpResult(await securityIpLookup(lookupIp)); } catch (e) { console.error(e); }
    setLoadingState('ip', false);
  };

  const runWhois = async () => {
    if (!whoisTarget) return;
    setLoadingState('whois', true);
    try { setWhoisResult(await securityWhois(whoisTarget)); } catch (e) { console.error(e); }
    setLoadingState('whois', false);
  };

  const runSubdomains = async () => {
    if (!subdomainTarget) return;
    setLoadingState('subdomains', true);
    try { setSubdomainResult(await securitySubdomains(subdomainTarget)); } catch (e) { console.error(e); }
    setLoadingState('subdomains', false);
  };

  const runTechFingerprint = async () => {
    if (!techUrl) return;
    setLoadingState('tech', true);
    try { setTechResult(await securityTechFingerprint(techUrl)); } catch (e) { console.error(e); }
    setLoadingState('tech', false);
  };

  const runTraceroute = async () => {
    if (!traceHost) return;
    setLoadingState('trace', true);
    try { setTraceResult(await securityTraceroute(traceHost)); } catch (e) { console.error(e); }
    setLoadingState('trace', false);
  };

  const runBannerGrab = async () => {
    if (!bannerHost) return;
    setLoadingState('banner', true);
    try { setBannerResult(await securityBannerGrab(bannerHost)); } catch (e) { console.error(e); }
    setLoadingState('banner', false);
  };

  const runWayback = async () => {
    if (!waybackUrl) return;
    setLoadingState('wayback', true);
    try { setWaybackResult(await securityWayback(waybackUrl)); } catch (e) { console.error(e); }
    setLoadingState('wayback', false);
  };

  const runFullScan = async () => {
    setLoadingState('full', true);
    try {
      const result = await securityFullScan(scanHost);
      if (result.port_scan) setPortScan(result.port_scan);
      if (result.system_audit) setAuditResult(result.system_audit);
      if (result.log_analysis) setLogResult(result.log_analysis);
      if (result.ssl_check) setSslResult(result.ssl_check);
      if (result.http_headers) setHeaderResult(result.http_headers);
      await loadDashboard();
    } catch (e) { console.error(e); }
    setLoadingState('full', false);
  };

  return (
    <div className="space-y-6 pb-10">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
            <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
              <Shield className="w-6 h-6 text-red-400" />
            </div>
            Security Center
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Blue Team Operations — Real-time threat detection & hardening</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Input value={scanHost} onChange={e => setScanHost(e.target.value)}
              placeholder="Target host" className="w-40 h-9 text-sm bg-secondary/30" />
          </div>
          <ScanButton onClick={runFullScan} loading={loading.full} icon={Scan} label="Full Scan" />
        </div>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-12 gap-4">
        <Card className="col-span-12 md:col-span-3 bg-card/60 border-border/40">
          <CardContent className="flex items-center gap-4 p-5">
            <ScoreRing score={dashboard?.overall_score} grade={dashboard?.overall_grade} size={80} />
            <div>
              <p className="text-sm font-medium">Security Score</p>
              <p className="text-xs text-muted-foreground">Based on latest scans</p>
            </div>
          </CardContent>
        </Card>
        <Card className="col-span-6 md:col-span-3 bg-card/60 border-border/40">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <ShieldAlert className="w-4 h-4 text-red-400" />
              <span className="text-sm font-medium">Active Alerts</span>
            </div>
            <p className="text-3xl font-bold">{dashboard?.alerts?.length ?? '—'}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {dashboard?.alerts?.filter(a => a.severity === 'critical').length || 0} critical
            </p>
          </CardContent>
        </Card>
        <Card className="col-span-6 md:col-span-3 bg-card/60 border-border/40">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <Wifi className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium">Open Ports</span>
            </div>
            <p className="text-3xl font-bold">{dashboard?.port_summary?.total_open ?? '—'}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {dashboard?.port_summary?.high_risk || 0} high risk
            </p>
          </CardContent>
        </Card>
        <Card className="col-span-12 md:col-span-3 bg-card/60 border-border/40">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-yellow-400" />
              <span className="text-sm font-medium">Log Events</span>
            </div>
            <p className="text-3xl font-bold">{dashboard?.log_summary?.total_events ?? '—'}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {dashboard?.log_summary?.brute_force_ips || 0} brute-force IPs
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Alerts Banner */}
      {dashboard?.alerts?.length > 0 && (
        <Card className="bg-red-500/5 border-red-500/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span className="text-sm font-semibold text-red-400">Active Alerts</span>
            </div>
            <div className="space-y-2">
              {dashboard.alerts.map((alert, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-red-500/5 border border-red-500/10">
                  <div className="flex items-center gap-3">
                    <SeverityBadge severity={alert.severity} />
                    <span className="text-sm">{alert.message}</span>
                  </div>
                  {alert.action && (
                    <code className="text-[11px] text-muted-foreground bg-secondary/40 px-2 py-1 rounded font-mono">
                      {alert.action}
                    </code>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-secondary/30">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="network">Network</TabsTrigger>
          <TabsTrigger value="system">System Audit</TabsTrigger>
          <TabsTrigger value="logs">Log Analysis</TabsTrigger>
          <TabsTrigger value="recon">Recon</TabsTrigger>
          <TabsTrigger value="threat-intel">Threat Intel</TabsTrigger>
        </TabsList>

        {/* ── Overview Tab ──────────────────────────────────────────── */}
        <TabsContent value="overview" className="space-y-4 mt-4">
          <div className="grid grid-cols-12 gap-4">
            {/* Quick Actions */}
            <Card className="col-span-12 lg:col-span-4 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Play className="w-4 h-4" /> Quick Scans
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <ScanButton onClick={runPortScan} loading={loading.port} icon={Wifi} label="Port Scan" />
                <ScanButton onClick={runAudit} loading={loading.audit} icon={Shield} label="System Audit" />
                <ScanButton onClick={runLogAnalysis} loading={loading.logs} icon={FileSearch} label="Log Analysis" />
                <ScanButton onClick={runSslCheck} loading={loading.ssl} icon={Lock} label="SSL Check" />
              </CardContent>
            </Card>

            {/* Latest Scans */}
            <Card className="col-span-12 lg:col-span-8 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Activity className="w-4 h-4" /> Scan History
                </CardTitle>
              </CardHeader>
              <CardContent>
                {history.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">No scans yet. Run a Full Scan to get started.</p>
                ) : (
                  <div className="space-y-2">
                    {history.map((scan, i) => (
                      <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg bg-secondary/20 border border-border/30">
                        <div className="flex items-center gap-3">
                          <Badge variant="outline" className="text-[10px] font-mono">{scan.type}</Badge>
                          <span className="text-sm">{scan.host || scan.url || 'localhost'}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {scan.scan_time ? new Date(scan.scan_time).toLocaleString() : '—'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ── Network Tab ───────────────────────────────────────────── */}
        <TabsContent value="network" className="space-y-4 mt-4">
          <div className="flex items-center gap-3 mb-4">
            <ScanButton onClick={runPortScan} loading={loading.port} icon={Wifi} label="Scan Ports" />
            <ScanButton onClick={runSslCheck} loading={loading.ssl} icon={Lock} label="Check SSL" />
          </div>

          <div className="grid grid-cols-12 gap-4">
            {/* Port Scan Results */}
            <Card className="col-span-12 lg:col-span-7 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Network className="w-4 h-4" /> Port Scan
                  {portScan && <SeverityBadge severity={portScan.risk_level} />}
                </CardTitle>
                {portScan && (
                  <CardDescription>
                    {portScan.summary?.total_open} open · {portScan.ports_scanned} scanned · {portScan.elapsed_seconds}s
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent>
                {!portScan ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">Run a port scan to see results</p>
                ) : portScan.open_ports?.length === 0 ? (
                  <div className="flex items-center gap-2 py-4 justify-center text-emerald-400">
                    <ShieldCheck className="w-5 h-5" />
                    <span className="text-sm font-medium">No open ports detected</span>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {portScan.open_ports.map((p, i) => (
                      <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg bg-secondary/20 border border-border/30">
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-sm font-bold w-16">{p.port}</span>
                          <span className="text-sm text-muted-foreground">{p.service}</span>
                        </div>
                        <SeverityBadge severity={p.risk} />
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* SSL Results */}
            <Card className="col-span-12 lg:col-span-5 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Lock className="w-4 h-4" /> SSL/TLS
                  {sslResult && !sslResult.error && <SeverityBadge severity={sslResult.risk_level} />}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!sslResult ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">Run SSL check to see results</p>
                ) : sslResult.error ? (
                  <p className="text-sm text-red-400 py-4 text-center">{sslResult.error}</p>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      {sslResult.valid ? <ShieldCheck className="w-5 h-5 text-emerald-400" /> : <ShieldX className="w-5 h-5 text-red-400" />}
                      <span className="text-sm font-medium">{sslResult.valid ? 'Valid Certificate' : 'INVALID Certificate'}</span>
                    </div>
                    <Separator className="bg-border/30" />
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div><span className="text-muted-foreground">Protocol:</span> <span className="font-mono">{sslResult.protocol}</span></div>
                      <div><span className="text-muted-foreground">Cipher:</span> <span className="font-mono text-xs">{sslResult.cipher}</span></div>
                      <div><span className="text-muted-foreground">Expires:</span> <span>{sslResult.days_remaining}d</span></div>
                      <div><span className="text-muted-foreground">Issuer:</span> <span>{sslResult.issuer?.organizationName || sslResult.issuer?.commonName || '—'}</span></div>
                    </div>
                    {sslResult.issues?.length > 0 && (
                      <div className="space-y-1.5 mt-2">
                        {sslResult.issues.map((iss, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm">
                            <SeverityBadge severity={iss.severity} />
                            <span>{iss.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ── System Audit Tab ──────────────────────────────────────── */}
        <TabsContent value="system" className="space-y-4 mt-4">
          <div className="flex items-center gap-3 mb-4">
            <ScanButton onClick={runAudit} loading={loading.audit} icon={Shield} label="Run System Audit" />
          </div>

          {!auditResult ? (
            <Card className="bg-card/60 border-border/40">
              <CardContent className="py-12 text-center text-muted-foreground">
                <Shield className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>Run a system audit to assess server hardening</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-12 gap-4">
              <Card className="col-span-12 lg:col-span-3 bg-card/60 border-border/40">
                <CardContent className="flex flex-col items-center gap-4 p-6">
                  <ScoreRing score={auditResult.summary?.score} grade={auditResult.summary?.grade} />
                  <div className="text-center">
                    <p className="text-sm font-medium">Hardening Score</p>
                    <p className="text-xs text-muted-foreground">{auditResult.hostname}</p>
                  </div>
                  <div className="w-full space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-red-400">Critical</span><span className="font-bold">{auditResult.summary?.critical}</span></div>
                    <div className="flex justify-between"><span className="text-orange-400">High</span><span className="font-bold">{auditResult.summary?.high}</span></div>
                    <div className="flex justify-between"><span className="text-yellow-400">Medium</span><span className="font-bold">{auditResult.summary?.medium}</span></div>
                  </div>
                </CardContent>
              </Card>

              <Card className="col-span-12 lg:col-span-9 bg-card/60 border-border/40">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Findings ({auditResult.findings?.length})</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 max-h-[500px] overflow-y-auto">
                  {auditResult.findings?.map((f, i) => (
                    <div key={i} className="p-3 rounded-lg bg-secondary/20 border border-border/30">
                      <div className="flex items-center gap-3 mb-1.5">
                        <SeverityBadge severity={f.severity} />
                        <Badge variant="outline" className="text-[10px] font-mono">{f.category}</Badge>
                        <span className="text-sm font-medium">{f.finding}</span>
                      </div>
                      <div className="flex items-center gap-2 ml-1">
                        <Terminal className="w-3 h-3 text-muted-foreground" />
                        <code className="text-[11px] text-emerald-400/80 font-mono">{f.remediation}</code>
                      </div>
                    </div>
                  ))}
                  {auditResult.findings?.length === 0 && (
                    <div className="flex items-center gap-2 py-6 justify-center text-emerald-400">
                      <ShieldCheck className="w-5 h-5" />
                      <span className="text-sm font-medium">System hardening looks good!</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* ── Log Analysis Tab ──────────────────────────────────────── */}
        <TabsContent value="logs" className="space-y-4 mt-4">
          <div className="flex items-center gap-3 mb-4">
            <ScanButton onClick={runLogAnalysis} loading={loading.logs} icon={FileSearch} label="Analyze Logs" />
          </div>

          {!logResult ? (
            <Card className="bg-card/60 border-border/40">
              <CardContent className="py-12 text-center text-muted-foreground">
                <FileSearch className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>Run log analysis to detect suspicious patterns</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-12 gap-4">
              {/* SIEM Stats */}
              <div className="col-span-12 grid grid-cols-4 gap-3">
                <Card className="bg-card/60 border-border/40">
                  <CardContent className="p-4 text-center">
                    <p className="text-2xl font-bold">{logResult.summary?.total_events}</p>
                    <p className="text-xs text-muted-foreground">Total Events</p>
                  </CardContent>
                </Card>
                <Card className="bg-red-500/5 border-red-500/20">
                  <CardContent className="p-4 text-center">
                    <p className="text-2xl font-bold text-red-400">{logResult.summary?.critical}</p>
                    <p className="text-xs text-muted-foreground">Critical</p>
                  </CardContent>
                </Card>
                <Card className="bg-orange-500/5 border-orange-500/20">
                  <CardContent className="p-4 text-center">
                    <p className="text-2xl font-bold text-orange-400">{logResult.summary?.high}</p>
                    <p className="text-xs text-muted-foreground">High</p>
                  </CardContent>
                </Card>
                <Card className="bg-yellow-500/5 border-yellow-500/20">
                  <CardContent className="p-4 text-center">
                    <p className="text-2xl font-bold text-yellow-400">{logResult.summary?.unique_ips}</p>
                    <p className="text-xs text-muted-foreground">Unique IPs</p>
                  </CardContent>
                </Card>
              </div>

              {/* Top Attackers */}
              {logResult.top_ips?.length > 0 && (
                <Card className="col-span-12 lg:col-span-5 bg-card/60 border-border/40">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Eye className="w-4 h-4 text-red-400" /> Top Threat IPs
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {logResult.top_ips.map((entry, i) => (
                      <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg bg-secondary/20 border border-border/30">
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-sm">{entry.ip}</span>
                          <SeverityBadge severity={entry.threat} />
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold">{entry.hits}</span>
                          <span className="text-xs text-muted-foreground">hits</span>
                          <Button size="sm" variant="ghost" className="h-6 w-6 p-0"
                            onClick={() => { setLookupIp(entry.ip); setActiveTab('threat-intel'); }}>
                            <Search className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* Events Feed */}
              <Card className={`col-span-12 ${logResult.top_ips?.length > 0 ? 'lg:col-span-7' : ''} bg-card/60 border-border/40`}>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Security Events ({logResult.events?.length})</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1.5 max-h-[500px] overflow-y-auto">
                  {logResult.events?.slice(-50).reverse().map((evt, i) => (
                    <div key={i} className="flex items-center gap-3 py-1.5 px-3 rounded bg-secondary/10 border border-border/20 text-sm">
                      <SeverityBadge severity={evt.severity} />
                      <Badge variant="outline" className="text-[10px] font-mono">{evt.type}</Badge>
                      {evt.ip && <span className="font-mono text-xs text-muted-foreground">{evt.ip}</span>}
                      <span className="text-xs text-muted-foreground truncate flex-1">{evt.line?.substring(0, 100)}</span>
                    </div>
                  ))}
                  {(!logResult.events || logResult.events.length === 0) && (
                    <div className="flex items-center gap-2 py-6 justify-center text-emerald-400">
                      <ShieldCheck className="w-5 h-5" />
                      <span className="text-sm font-medium">No suspicious events detected</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* ── Recon Tab ─────────────────────────────────────────────── */}
        <TabsContent value="recon" className="space-y-4 mt-4">
          <div className="grid grid-cols-12 gap-4">
            {/* WHOIS Lookup */}
            <Card className="col-span-12 lg:col-span-6 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Search className="w-4 h-4" /> WHOIS Lookup
                </CardTitle>
                <CardDescription>Domain/IP registration & ownership info</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input value={whoisTarget} onChange={e => setWhoisTarget(e.target.value)}
                    placeholder="example.com or 8.8.8.8" className="h-9 text-sm bg-secondary/30"
                    onKeyDown={e => e.key === 'Enter' && runWhois()} />
                  <ScanButton onClick={runWhois} loading={loading.whois} icon={Search} label="Lookup" />
                </div>
                {whoisResult && !whoisResult.error && whoisResult.parsed && (
                  <div className="space-y-2 mt-3">
                    {Object.entries(whoisResult.parsed).map(([key, val]) => (
                      <div key={key} className="flex items-start gap-2 py-1.5 px-3 rounded-lg bg-secondary/20 border border-border/30">
                        <span className="text-xs text-muted-foreground min-w-[100px] capitalize">{key.replace(/_/g, ' ')}:</span>
                        <span className="text-xs font-mono break-all">
                          {Array.isArray(val) ? val.join(', ') : String(val)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {whoisResult?.error && (
                  <p className="text-sm text-red-400 mt-2">{whoisResult.error}</p>
                )}
              </CardContent>
            </Card>

            {/* Subdomain Enumeration */}
            <Card className="col-span-12 lg:col-span-6 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Layers className="w-4 h-4" /> Subdomain Enumeration
                </CardTitle>
                <CardDescription>Discover subdomains via CT logs & DNS brute-force</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input value={subdomainTarget} onChange={e => setSubdomainTarget(e.target.value)}
                    placeholder="example.com" className="h-9 text-sm bg-secondary/30"
                    onKeyDown={e => e.key === 'Enter' && runSubdomains()} />
                  <ScanButton onClick={runSubdomains} loading={loading.subdomains} icon={Search} label="Enumerate" />
                </div>
                {subdomainResult && !subdomainResult.error && (
                  <div className="space-y-2 mt-3">
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-muted-foreground">Found: <span className="font-bold text-foreground">{subdomainResult.total_found}</span></span>
                      {subdomainResult.sources && Object.entries(subdomainResult.sources).map(([src, count]) => (
                        <Badge key={src} variant="outline" className="text-[10px] font-mono">{src}: {count}</Badge>
                      ))}
                    </div>
                    <div className="max-h-[300px] overflow-y-auto space-y-1">
                      {subdomainResult.subdomains?.map((sub, i) => (
                        <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-secondary/20 border border-border/30">
                          <span className="text-xs font-mono">{sub.subdomain}</span>
                          <span className="text-[10px] text-muted-foreground font-mono">{sub.ips?.join(', ') || '—'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Technology Fingerprinting */}
            <Card className="col-span-12 lg:col-span-6 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Code className="w-4 h-4" /> Technology Fingerprint
                </CardTitle>
                <CardDescription>Detect web technologies, CMS, frameworks & CDN</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input value={techUrl} onChange={e => setTechUrl(e.target.value)}
                    placeholder="https://example.com" className="h-9 text-sm bg-secondary/30"
                    onKeyDown={e => e.key === 'Enter' && runTechFingerprint()} />
                  <ScanButton onClick={runTechFingerprint} loading={loading.tech} icon={Search} label="Scan" />
                </div>
                {techResult && !techResult.error && (
                  <div className="space-y-3 mt-3">
                    {techResult.meta_info?.title && (
                      <p className="text-sm font-medium truncate">{techResult.meta_info.title}</p>
                    )}
                    <div className="flex flex-wrap gap-1.5">
                      {techResult.technologies?.map((tech, i) => (
                        <Badge key={i} variant="outline" className={`text-[10px] font-mono ${
                          tech.category === 'server' ? 'border-red-500/40 text-red-400' :
                          tech.category === 'framework' ? 'border-blue-500/40 text-blue-400' :
                          tech.category === 'cms' ? 'border-purple-500/40 text-purple-400' :
                          tech.category === 'cdn' ? 'border-green-500/40 text-green-400' :
                          tech.category === 'analytics' ? 'border-yellow-500/40 text-yellow-400' :
                          'border-zinc-500/40 text-zinc-400'
                        }`}>
                          {tech.name}
                        </Badge>
                      ))}
                    </div>
                    {techResult.server_info && Object.keys(techResult.server_info).length > 0 && (
                      <div className="space-y-1">
                        {Object.entries(techResult.server_info).map(([k, v]) => (
                          <div key={k} className="flex gap-2 text-xs">
                            <span className="text-muted-foreground capitalize">{k.replace(/_/g, ' ')}:</span>
                            <span className="font-mono text-orange-400">{v}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {techResult?.error && <p className="text-sm text-red-400 mt-2">{techResult.error}</p>}
              </CardContent>
            </Card>

            {/* DNS Lookup */}
            <Card className="col-span-12 lg:col-span-6 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Globe className="w-4 h-4" /> DNS Reconnaissance
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input value={dnsTarget} onChange={e => setDnsTarget(e.target.value)}
                    placeholder="example.com" className="h-9 text-sm bg-secondary/30"
                    onKeyDown={e => e.key === 'Enter' && runDnsCheck()} />
                  <ScanButton onClick={runDnsCheck} loading={loading.dns} icon={Search} label="Lookup" />
                </div>
                {dnsResult && !dnsResult.error && (
                  <div className="space-y-2 mt-3">
                    {Object.entries(dnsResult.records || {}).map(([type, records]) => (
                      <div key={type} className="p-2.5 rounded-lg bg-secondary/20 border border-border/30">
                        <Badge variant="outline" className="text-[10px] font-mono mb-1.5">{type}</Badge>
                        {records.map((r, i) => (
                          <p key={i} className="text-xs font-mono text-muted-foreground pl-2">{r}</p>
                        ))}
                      </div>
                    ))}
                    {dnsResult.issues?.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {dnsResult.issues.map((iss, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm">
                            <SeverityBadge severity={iss.severity} />
                            <span>{iss.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-3 mt-2 text-xs">
                      <span>SPF: {dnsResult.email_security?.spf ? '✅' : '❌'}</span>
                      <span>DMARC: {dnsResult.email_security?.dmarc ? '✅' : '❌'}</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* HTTP Headers */}
            <Card className="col-span-12 lg:col-span-6 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Server className="w-4 h-4" /> HTTP Security Headers
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input value={headerUrl} onChange={e => setHeaderUrl(e.target.value)}
                    placeholder="https://example.com" className="h-9 text-sm bg-secondary/30"
                    onKeyDown={e => e.key === 'Enter' && runHeaderCheck()} />
                  <ScanButton onClick={runHeaderCheck} loading={loading.headers} icon={Search} label="Check" />
                </div>
                {headerResult && !headerResult.error && (
                  <div className="space-y-3 mt-3">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium">Score:</span>
                      <span className={`text-lg font-bold ${GRADE_COLORS[headerResult.grade]}`}>
                        {headerResult.grade} ({headerResult.score}%)
                      </span>
                    </div>
                    <Progress value={headerResult.score} className="h-2" />
                    {headerResult.missing_headers?.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1.5">Missing Headers:</p>
                        {headerResult.missing_headers.map((h, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm py-1">
                            <SeverityBadge severity={h.severity} />
                            <span className="font-mono text-xs">{h.header}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {headerResult.info_leaked?.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1.5">Information Leaked:</p>
                        {headerResult.info_leaked.map((h, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm py-1">
                            <AlertTriangle className="w-3 h-3 text-orange-400" />
                            <span className="font-mono text-xs">{h.header}: {h.value}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Banner Grab */}
            <Card className="col-span-12 lg:col-span-6 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Radio className="w-4 h-4" /> Banner Grabbing
                </CardTitle>
                <CardDescription>Grab service banners to identify software versions</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input value={bannerHost} onChange={e => setBannerHost(e.target.value)}
                    placeholder="example.com" className="h-9 text-sm bg-secondary/30"
                    onKeyDown={e => e.key === 'Enter' && runBannerGrab()} />
                  <ScanButton onClick={runBannerGrab} loading={loading.banner} icon={Search} label="Grab" />
                </div>
                {bannerResult && !bannerResult.error && (
                  <div className="space-y-1.5 mt-3 max-h-[300px] overflow-y-auto">
                    <p className="text-xs text-muted-foreground">{bannerResult.total_responsive} responsive ports</p>
                    {bannerResult.banners?.map((b, i) => (
                      <div key={i} className="p-2.5 rounded-lg bg-secondary/20 border border-border/30">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-sm font-bold">{b.port}</span>
                          <Badge variant="outline" className="text-[10px] font-mono">{b.service}</Badge>
                          {b.detected && <span className="text-[10px] text-orange-400 font-mono">{b.detected}</span>}
                        </div>
                        {b.banner && (
                          <pre className="text-[10px] text-muted-foreground font-mono whitespace-pre-wrap break-all max-h-20 overflow-hidden">
                            {b.banner.substring(0, 200)}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Traceroute */}
            <Card className="col-span-12 lg:col-span-6 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Route className="w-4 h-4" /> Traceroute
                </CardTitle>
                <CardDescription>Map the network path to a target</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input value={traceHost} onChange={e => setTraceHost(e.target.value)}
                    placeholder="example.com" className="h-9 text-sm bg-secondary/30"
                    onKeyDown={e => e.key === 'Enter' && runTraceroute()} />
                  <ScanButton onClick={runTraceroute} loading={loading.trace} icon={Route} label="Trace" />
                </div>
                {traceResult && !traceResult.error && (
                  <div className="space-y-1 mt-3 max-h-[300px] overflow-y-auto">
                    <p className="text-xs text-muted-foreground mb-2">
                      Target: {traceResult.target_ip} · {traceResult.total_hops} hops
                    </p>
                    {traceResult.hops?.map((hop, i) => (
                      <div key={i} className="flex items-center gap-3 py-1.5 px-3 rounded bg-secondary/20 border border-border/30 text-xs font-mono">
                        <span className="w-6 text-muted-foreground font-bold">{hop.hop}</span>
                        <span className="w-32">{hop.ip || '* * *'}</span>
                        <span className="text-muted-foreground truncate flex-1">{hop.hostname || ''}</span>
                        <span className="text-blue-400">{hop.rtts?.filter(Boolean).map(r => r + 'ms').join(' / ') || '*'}</span>
                      </div>
                    ))}
                  </div>
                )}
                {traceResult?.error && <p className="text-sm text-red-400 mt-2">{traceResult.error}</p>}
              </CardContent>
            </Card>

            {/* Wayback Machine */}
            <Card className="col-span-12 lg:col-span-6 bg-card/60 border-border/40">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="w-4 h-4" /> Wayback Machine
                </CardTitle>
                <CardDescription>Internet Archive historical snapshots</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Input value={waybackUrl} onChange={e => setWaybackUrl(e.target.value)}
                    placeholder="example.com" className="h-9 text-sm bg-secondary/30"
                    onKeyDown={e => e.key === 'Enter' && runWayback()} />
                  <ScanButton onClick={runWayback} loading={loading.wayback} icon={Search} label="Search" />
                </div>
                {waybackResult && !waybackResult.error && (
                  <div className="space-y-2 mt-3">
                    <p className="text-xs text-muted-foreground">{waybackResult.total_snapshots} snapshots found</p>
                    {waybackResult.latest_snapshot && (
                      <div className="p-2.5 rounded-lg bg-secondary/20 border border-border/30">
                        <p className="text-xs text-muted-foreground">Latest snapshot:</p>
                        <a href={waybackResult.latest_snapshot.url} target="_blank" rel="noopener noreferrer"
                          className="text-xs font-mono text-blue-400 hover:underline flex items-center gap-1">
                          {waybackResult.latest_snapshot.timestamp?.substring(0, 8)} <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    )}
                    <div className="max-h-[250px] overflow-y-auto space-y-1">
                      {waybackResult.snapshots?.map((snap, i) => (
                        <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded bg-secondary/20 border border-border/30">
                          <span className="text-xs font-mono">{snap.date || snap.timestamp}</span>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px] font-mono">{snap.statuscode}</Badge>
                            <a href={snap.wayback_url} target="_blank" rel="noopener noreferrer"
                              className="text-blue-400 hover:text-blue-300">
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {waybackResult?.error && <p className="text-sm text-red-400 mt-2">{waybackResult.error}</p>}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ── Threat Intel Tab ──────────────────────────────────────── */}
        <TabsContent value="threat-intel" className="space-y-4 mt-4">
          <Card className="bg-card/60 border-border/40">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <MapPin className="w-4 h-4" /> IP Reputation Lookup
              </CardTitle>
              <CardDescription>Check an IP against local logs and threat intelligence sources</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input value={lookupIp} onChange={e => setLookupIp(e.target.value)}
                  placeholder="192.168.1.1" className="h-9 text-sm bg-secondary/30 max-w-xs"
                  onKeyDown={e => e.key === 'Enter' && runIpLookup()} />
                <ScanButton onClick={runIpLookup} loading={loading.ip} icon={Search} label="Lookup" />
              </div>
              {ipResult && !ipResult.error && (
                <div className="grid grid-cols-12 gap-4 mt-4">
                  <div className="col-span-12 md:col-span-4 p-4 rounded-lg bg-secondary/20 border border-border/30">
                    <div className="flex items-center gap-3 mb-3">
                      <div className={`p-2 rounded-lg ${ipResult.verdict === 'malicious' ? 'bg-red-500/20' : ipResult.verdict === 'suspicious' ? 'bg-yellow-500/20' : 'bg-emerald-500/20'}`}>
                        {ipResult.verdict === 'malicious' ? <ShieldX className="w-5 h-5 text-red-400" /> :
                         ipResult.verdict === 'suspicious' ? <ShieldAlert className="w-5 h-5 text-yellow-400" /> :
                         <ShieldCheck className="w-5 h-5 text-emerald-400" />}
                      </div>
                      <div>
                        <p className="text-sm font-bold capitalize">{ipResult.verdict}</p>
                        <p className="text-xs text-muted-foreground">Risk: {ipResult.risk_score}/100</p>
                      </div>
                    </div>
                    <Progress value={ipResult.risk_score} className="h-2" />
                  </div>

                  <div className="col-span-12 md:col-span-4 p-4 rounded-lg bg-secondary/20 border border-border/30">
                    <p className="text-xs text-muted-foreground mb-2">Geolocation</p>
                    <div className="space-y-1.5 text-sm">
                      <p><span className="text-muted-foreground">Country:</span> {ipResult.geo?.country || '—'}</p>
                      <p><span className="text-muted-foreground">City:</span> {ipResult.geo?.city || '—'}</p>
                      <p><span className="text-muted-foreground">Org:</span> {ipResult.geo?.org || '—'}</p>
                    </div>
                  </div>

                  <div className="col-span-12 md:col-span-4 p-4 rounded-lg bg-secondary/20 border border-border/30">
                    <p className="text-xs text-muted-foreground mb-2">Details</p>
                    <div className="space-y-1.5 text-sm">
                      <p><span className="text-muted-foreground">rDNS:</span> <span className="font-mono text-xs">{ipResult.reverse_dns || '—'}</span></p>
                      <p><span className="text-muted-foreground">Local hits:</span> {ipResult.local_hits}</p>
                      <p><span className="text-muted-foreground">Hostname:</span> <span className="font-mono text-xs">{ipResult.geo?.hostname || '—'}</span></p>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
