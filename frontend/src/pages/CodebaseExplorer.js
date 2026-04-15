import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import {
  Code2, Search, FolderTree, RefreshCw, Loader2, FileCode, GitBranch,
  ArrowRight, Database, Braces, Eye, Network, Layers
} from 'lucide-react';
import { getCodebaseGraph, searchCodebase, indexRag, searchRag } from '../lib/api';
import { toast } from 'sonner';

export default function CodebaseExplorer() {
  const [tab, setTab] = useState('search'); // search | graph | rag
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState('symbol');
  const [results, setResults] = useState([]);
  const [graph, setGraph] = useState(null);
  const [ragResults, setRagResults] = useState([]);
  const [ragQuery, setRagQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await searchCodebase(query, searchType);
      setResults(data.results || []);
    } catch (e) {
      toast.error('Search failed');
    }
    setLoading(false);
  };

  const handleBuildGraph = async () => {
    setLoading(true);
    try {
      const data = await getCodebaseGraph();
      setGraph(data);
      toast.success(`Graph built: ${data.nodes} files, ${data.edges} connections`);
    } catch (e) {
      toast.error('Failed to build graph');
    }
    setLoading(false);
  };

  const handleIndexRag = async () => {
    setIndexing(true);
    try {
      await indexRag('/tmp/ombra_workspace');
      toast.success('RAG index built successfully');
    } catch (e) {
      toast.error('Indexing failed');
    }
    setIndexing(false);
  };

  const handleRagSearch = async () => {
    if (!ragQuery.trim()) return;
    setLoading(true);
    try {
      const data = await searchRag(ragQuery, 'all', 8);
      setRagResults(data.results || []);
    } catch (e) {
      toast.error('RAG search failed');
    }
    setLoading(false);
  };

  const tabs = [
    { id: 'search', icon: Search, label: 'Code Search' },
    { id: 'graph', icon: Network, label: 'Dependency Graph' },
    { id: 'rag', icon: Database, label: 'Semantic Search' },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
            <Code2 className="w-5 h-5 text-cyan-400" />
          </div>
          Codebase Explorer
        </h1>
        <p className="text-muted-foreground mt-1">
          Search symbols, browse dependencies, and find code semantically
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-secondary/30 rounded-lg w-fit">
        {tabs.map(t => (
          <Button
            key={t.id}
            variant={tab === t.id ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setTab(t.id)}
            className={tab === t.id ? '' : 'text-muted-foreground'}
          >
            <t.icon className="w-4 h-4 mr-1.5" />
            {t.label}
          </Button>
        ))}
      </div>

      {/* Code Search Tab */}
      {tab === 'search' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <Card className="bg-card/50 border-border/40">
            <CardContent className="p-4">
              <div className="flex gap-2 mb-3">
                {['symbol', 'text', 'file'].map(t => (
                  <Button
                    key={t}
                    variant={searchType === t ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSearchType(t)}
                    className="capitalize"
                  >
                    {t}
                  </Button>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  placeholder={searchType === 'symbol' ? 'Search functions, classes...' :
                    searchType === 'file' ? 'Search file names...' : 'Search code text...'}
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  className="flex-1"
                />
                <Button onClick={handleSearch} disabled={loading}>
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> :
                    <Search className="w-4 h-4" />}
                </Button>
              </div>
            </CardContent>
          </Card>

          {results.length > 0 && (
            <div className="space-y-2">
              {results.map((r, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                >
                  <Card className="bg-card/50 border-border/40 hover:border-cyan-500/30 transition-colors">
                    <CardContent className="p-3">
                      <div className="flex items-start gap-2">
                        <FileCode className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-sm font-medium text-cyan-300">
                              {r.name || r.symbol || r}
                            </span>
                            {r.type && (
                              <Badge variant="outline" className="text-[10px] h-4">{r.type}</Badge>
                            )}
                          </div>
                          {r.file && (
                            <p className="text-xs text-muted-foreground font-mono mt-0.5 truncate">
                              {r.file}{r.line ? `:${r.line}` : ''}
                            </p>
                          )}
                          {r.preview && (
                            <pre className="text-[11px] text-muted-foreground mt-1 bg-background/50 rounded p-1.5 overflow-x-auto">
                              {r.preview}
                            </pre>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      )}

      {/* Graph Tab */}
      {tab === 'graph' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <Card className="bg-card/50 border-border/40">
            <CardContent className="p-6 text-center">
              <Network className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <h3 className="font-semibold mb-2">Dependency Graph</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Build a graph of file dependencies and imports across your workspace
              </p>
              <Button onClick={handleBuildGraph} disabled={loading}>
                {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> :
                  <GitBranch className="w-4 h-4 mr-2" />}
                Build Graph
              </Button>
            </CardContent>
          </Card>

          {graph && (
            <div className="grid grid-cols-2 gap-4">
              <Card className="bg-card/50 border-border/40">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Layers className="w-4 h-4 text-cyan-400" />
                    <span className="font-semibold">Graph Stats</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Files</span>
                      <span className="font-mono">{graph.nodes}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Dependencies</span>
                      <span className="font-mono">{graph.edges}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card className="bg-card/50 border-border/40">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <FolderTree className="w-4 h-4 text-cyan-400" />
                    <span className="font-semibold">Files</span>
                  </div>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {(graph.files || []).slice(0, 50).map((f, i) => (
                      <p key={i} className="text-xs font-mono text-muted-foreground truncate">{f}</p>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </motion.div>
      )}

      {/* RAG Tab */}
      {tab === 'rag' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <Card className="bg-card/50 border-border/40">
            <CardContent className="p-4 space-y-3">
              <div className="flex gap-2">
                <Button onClick={handleIndexRag} variant="outline" size="sm" disabled={indexing}>
                  {indexing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> :
                    <Database className="w-4 h-4 mr-2" />}
                  {indexing ? 'Indexing...' : 'Index Workspace'}
                </Button>
              </div>
              <div className="flex gap-2">
                <Input
                  placeholder="Search semantically — e.g. 'authentication middleware'"
                  value={ragQuery}
                  onChange={e => setRagQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleRagSearch()}
                  className="flex-1"
                />
                <Button onClick={handleRagSearch} disabled={loading}>
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> :
                    <Search className="w-4 h-4" />}
                </Button>
              </div>
            </CardContent>
          </Card>

          {ragResults.length > 0 && (
            <div className="space-y-2">
              {ragResults.map((r, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Card className="bg-card/50 border-border/40">
                    <CardContent className="p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          {r.file && (
                            <p className="text-xs font-mono text-cyan-400 mb-1 truncate">{r.file}</p>
                          )}
                          <pre className="text-[11px] text-muted-foreground bg-background/50 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                            {r.text}
                          </pre>
                        </div>
                        <Badge variant="outline" className="text-[10px] flex-shrink-0">
                          {(r.score * 100).toFixed(0)}%
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
