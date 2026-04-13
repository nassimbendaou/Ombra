import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Separator } from '../components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import {
  Sparkles, Plus, Upload, Trash2, ToggleLeft, ToggleRight,
  FileText, Eye, X, Check, Loader2, BookOpen, Zap
} from 'lucide-react';
import { getSkills, activateSkill, deactivateSkill, deleteSkill, createSkill } from '../lib/api';
import { toast } from 'sonner';

export default function Skills() {
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [previewSkill, setPreviewSkill] = useState(null);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [form, setForm] = useState({ id: '', content: '' });
  const [formMode, setFormMode] = useState('file'); // 'file' | 'text'
  const fileInputRef = useRef(null);

  const fetchSkills = () => {
    setLoading(true);
    getSkills()
      .then(data => { setSkills(data || []); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { fetchSkills(); }, []);

  const handleToggle = async (skill) => {
    try {
      if (skill.active) {
        await deactivateSkill(skill.id);
        toast.success(`Skill "${skill.name}" deactivated`);
      } else {
        await activateSkill(skill.id);
        toast.success(`Skill "${skill.name}" activated`);
      }
      fetchSkills();
    } catch (e) {
      toast.error('Failed to toggle skill');
    }
  };

  const handleDelete = async (skill) => {
    try {
      await deleteSkill(skill.id);
      toast.success(`Skill "${skill.name}" removed`);
      fetchSkills();
    } catch (e) {
      toast.error('Failed to delete skill');
    }
  };

  const handleFileRead = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target.result;
      // Auto-detect id from filename (e.g. my-skill.md → my-skill)
      const autoId = file.name.replace(/\.(md|txt|markdown)$/i, '').toLowerCase().replace(/\s+/g, '-');
      setForm(prev => ({ id: prev.id || autoId, content }));
    };
    reader.readAsText(file);
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileRead(file);
  };

  const handleFileInput = (e) => {
    const file = e.target.files[0];
    if (file) handleFileRead(file);
  };

  const handleUpload = async () => {
    if (!form.id.trim()) { toast.error('Skill ID is required'); return; }
    if (!form.content.trim()) { toast.error('Skill content is required'); return; }
    setUploading(true);
    try {
      await createSkill(form.id.trim(), form.content.trim());
      toast.success(`Skill "${form.id}" installed`);
      setShowUpload(false);
      setForm({ id: '', content: '' });
      fetchSkills();
    } catch (e) {
      toast.error('Failed to install skill: ' + (e.message || 'Unknown error'));
    } finally {
      setUploading(false);
    }
  };

  const activeCount = skills.filter(s => s.active).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Skills</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Inject domain knowledge into Ombra's context.{' '}
            <span className="font-mono-ombra text-xs">{activeCount}/{skills.length} active</span>
          </p>
        </div>
        <Button onClick={() => setShowUpload(true)}>
          <Upload className="w-4 h-4 mr-2" /> Upload Skill
        </Button>
      </div>

      {/* Skill grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-40 bg-card/40 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : skills.length === 0 ? (
        <Card className="bg-card/60 border-dashed border-border/60">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <BookOpen className="w-7 h-7 text-primary/60" />
            </div>
            <h3 className="text-sm font-semibold">No skills installed</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              Upload a SKILL.md file to give Ombra domain-specific knowledge that gets injected into its context automatically.
            </p>
            <Button variant="outline" className="mt-4" onClick={() => setShowUpload(true)}>
              <Upload className="w-4 h-4 mr-2" /> Upload your first skill
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {skills.map((skill) => (
            <motion.div
              key={skill.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <Card className={`bg-card/80 backdrop-blur border-border/60 hover:border-border/80 transition-all h-full ${skill.active ? 'ring-1 ring-primary/20' : ''}`}>
                <CardContent className="p-5 flex flex-col h-full">
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${skill.active ? 'bg-primary/20' : 'bg-muted/40'}`}>
                        <Sparkles className={`w-4 h-4 ${skill.active ? 'text-primary' : 'text-muted-foreground/40'}`} />
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold truncate">{skill.name || skill.id}</h3>
                        <p className="text-[10px] font-mono-ombra text-muted-foreground truncate">{skill.id}</p>
                      </div>
                    </div>
                    <Badge
                      variant={skill.active ? 'default' : 'outline'}
                      className="text-[10px] flex-shrink-0"
                    >
                      {skill.active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>

                  <p className="text-xs text-muted-foreground line-clamp-3 flex-1">
                    {skill.purpose || skill.description || 'No description available.'}
                  </p>

                  <div className="flex items-center gap-1.5 mt-4 pt-3 border-t border-border/40">
                    <Button
                      variant={skill.active ? 'default' : 'outline'}
                      size="sm"
                      className="flex-1 text-xs h-7"
                      onClick={() => handleToggle(skill)}
                    >
                      {skill.active
                        ? <><ToggleRight className="w-3.5 h-3.5 mr-1" /> Deactivate</>
                        : <><ToggleLeft className="w-3.5 h-3.5 mr-1" /> Activate</>
                      }
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      title="Preview"
                      onClick={() => setPreviewSkill(skill)}
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                      title="Delete"
                      onClick={() => handleDelete(skill)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {/* Upload Dialog */}
      <Dialog open={showUpload} onOpenChange={setShowUpload}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Upload className="w-4 h-4 text-primary" /> Upload Skill
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Skill ID */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Skill ID</label>
              <Input
                placeholder="e.g. code-review"
                value={form.id}
                onChange={e => setForm(prev => ({ ...prev, id: e.target.value.toLowerCase().replace(/\s+/g, '-') }))}
                className="font-mono-ombra text-sm"
              />
              <p className="text-[11px] text-muted-foreground">Lowercase, hyphens only. Auto-filled from filename.</p>
            </div>

            {/* Input mode tabs */}
            <div className="flex rounded-lg overflow-hidden border border-border/60 w-fit">
              <button
                className={`px-3 py-1.5 text-xs transition-colors ${formMode === 'file' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                onClick={() => setFormMode('file')}
              >
                <FileText className="w-3 h-3 inline mr-1" /> File
              </button>
              <button
                className={`px-3 py-1.5 text-xs transition-colors ${formMode === 'text' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                onClick={() => setFormMode('text')}
              >
                <Zap className="w-3 h-3 inline mr-1" /> Paste
              </button>
            </div>

            {formMode === 'file' ? (
              /* Drop zone */
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                  dragOver
                    ? 'border-primary bg-primary/5'
                    : 'border-border/60 hover:border-primary/50 hover:bg-primary/5'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".md,.txt,.markdown"
                  className="hidden"
                  onChange={handleFileInput}
                />
                <Upload className="w-8 h-8 text-muted-foreground/40 mx-auto mb-2" />
                {form.content ? (
                  <div className="space-y-1">
                    <div className="flex items-center justify-center gap-2 text-sm text-primary">
                      <Check className="w-4 h-4" /> File loaded
                    </div>
                    <p className="text-xs text-muted-foreground">{form.content.length} characters · click to replace</p>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-muted-foreground">Drop a <span className="font-mono-ombra text-xs">SKILL.md</span> file or click to browse</p>
                    <p className="text-xs text-muted-foreground/50 mt-1">Accepts .md, .txt, .markdown</p>
                  </>
                )}
              </div>
            ) : (
              /* Paste area */
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Skill Content (Markdown)</label>
                <textarea
                  value={form.content}
                  onChange={e => setForm(prev => ({ ...prev, content: e.target.value }))}
                  placeholder="# Skill Name&#10;&#10;## Purpose&#10;Describe what this skill does...&#10;&#10;## Instructions&#10;Detailed instructions injected into context."
                  className="w-full h-48 bg-secondary/30 border border-border/60 rounded-lg p-3 text-xs font-mono-ombra resize-none focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => { setShowUpload(false); setForm({ id: '', content: '' }); }}>
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={uploading || !form.id.trim() || !form.content.trim()}
            >
              {uploading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
              Install Skill
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog open={!!previewSkill} onOpenChange={() => setPreviewSkill(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-primary" />
              {previewSkill?.name || previewSkill?.id}
              <Badge variant="outline" className="text-[10px] font-mono-ombra ml-1">{previewSkill?.id}</Badge>
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto">
            <pre className="text-xs font-mono-ombra whitespace-pre-wrap bg-secondary/20 rounded-lg p-4 leading-relaxed">
              {previewSkill?.content || '(content not loaded — use GET /api/skills/:id)'}
            </pre>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPreviewSkill(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
