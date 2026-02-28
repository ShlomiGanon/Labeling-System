import React, { useState, useEffect } from 'react';
import * as api from './api/client';

/**
 * Main App Component
 * ------------------
 * This is the heart of the frontend. It manages which "screen" the user sees:
 * - 'loading': Shows a spinner while waiting for data.
 * - 'login': Where users enter their name.
 * - 'projects': A list of all labeling projects.
 * - 'new-project': A form to create a new project.
 * - 'task': The actual labeling screen for one row of data.
 */
export default function App() {
  const [screen, setScreen] = useState('loading');
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [currentTask, setCurrentTask] = useState(null);
  const [showContinueDialog, setShowContinueDialog] = useState(false);
  const [rowsRemaining, setRowsRemaining] = useState(0);
  const [isProjectFinished, setIsProjectFinished] = useState(false);
  const [error, setError] = useState('');

  // ---------------------------------------------------------------------------
  // Login & Session logic
  // ---------------------------------------------------------------------------

  useEffect(() => {
    // When the page first loads, check if we are already logged in
    async function checkSession() {
      const { ok, data } = await api.getMe();
      if (ok && data.user_name) {
        setUser(data.user_name);
        fetchProjects();
      } else {
        setScreen('login');
      }
    }
    checkSession();
  }, []);

  const handleLogin = async (userName) => {
    setError('');
    const { ok, data } = await api.login(userName);
    if (ok) {
      setUser(data.user_name);
      fetchProjects();
    } else {
      setError(data.error || 'Login failed');
    }
  };

  const handleLogout = async () => {
    await api.logout();
    setUser(null);
    setScreen('login');
  };

  // ---------------------------------------------------------------------------
  // Project logic (Listing and Creating)
  // ---------------------------------------------------------------------------

  const fetchProjects = async () => {
    setScreen('loading');
    const { ok, data } = await api.getProjects();
    if (ok) {
      setProjects(data.projects);
      setScreen('projects');
    } else {
      setError('Failed to load projects');
      setScreen('projects');
    }
  };

  const handleCreateProject = async (projectData) => {
    setError('');
    const { ok, data } = await api.createProject(projectData);
    if (ok) {
      fetchProjects();
    } else {
      setError(data.error || 'Failed to create project');
    }
  };

  const handleUpdateProject = async (projectId, projectData) => {
    setError('');
    const { ok, data } = await api.updateProject(projectId, projectData);
    if (ok) {
      fetchProjects();
    } else {
      setError(data.error || 'Failed to update project');
    }
  };

  const handleDeleteProject = async (projectId, deleteFiles) => {
    const { ok, data } = await api.deleteProject(projectId, deleteFiles);
    if (ok) {
      setProjects(prev => prev.filter(p => p.id !== projectId));
    } else {
      setError(data.error || 'שגיאה במחיקת הפרויקט');
    }
  };

  const handleSelectProject = (project) => {
    setActiveProject(project);
    fetchNextTask(project.id);
  };

  // ---------------------------------------------------------------------------
  // Task logic (Getting the next row to label)
  // ---------------------------------------------------------------------------

  const fetchNextTask = async (projectId) => {
    setScreen('loading');
    const { ok, data } = await api.getTask(projectId);
    if (ok) {
      if (data.finished) {
        setCurrentTask(null);
        setIsProjectFinished(true);
      } else {
        setCurrentTask(data);
        setIsProjectFinished(false);
      }
      setScreen('task');
    } else {
      setError(data.error || 'Failed to fetch task');
      setScreen('projects');
    }
  };

  const handleSubmitLabel = async (payload) => {
    setError('');
    // Each label needs the row_id of what is being labeled
    const fullPayload = { ...payload, row_id: currentTask.row_id };
    const { ok, data } = await api.submitLabel(activeProject.id, fullPayload);
    if (ok) {
      setRowsRemaining(data.rows_remaining);
      setIsProjectFinished(data.is_finished);
      setShowContinueDialog(true);
    } else {
      setError(data.error || 'Failed to submit label');
    }
  };

  // ---------------------------------------------------------------------------
  // Rendering the current screen
  // ---------------------------------------------------------------------------

  const renderScreen = () => {
    switch (screen) {
      case 'loading':
        return <LoadingScreen />;
      case 'login':
        return <LoginScreen onLogin={handleLogin} error={error} />;
      case 'projects':
        return (
          <ProjectsScreen
            projects={projects}
            onSelect={handleSelectProject}
            onCreateNew={() => setScreen('new-project')}
            onEdit={(p) => { setActiveProject(p); setScreen('edit-project'); }}
            onDelete={handleDeleteProject}
            error={error}
          />
        );
      case 'new-project':
        return (
          <ProjectFormScreen
            onSubmit={handleCreateProject}
            onBack={() => setScreen('projects')}
            error={error}
          />
        );
      case 'edit-project':
        return (
          <ProjectFormScreen
            key={activeProject?.id}
            initialData={activeProject}
            onSubmit={(data) => handleUpdateProject(activeProject.id, data)}
            onBack={() => setScreen('projects')}
            error={error}
            isEdit={true}
          />
        );
      case 'task':
        return (
          <TaskScreen
            project={activeProject}
            task={currentTask}
            isFinished={isProjectFinished}
            onSubmit={handleSubmitLabel}
            onExit={() => {
              setActiveProject(null);
              fetchProjects();
            }}
            error={error}
          />
        );
      default:
        return <div>Unknown screen</div>;
    }
  };

  return (
    <div className="app-wrapper">
      {user && (
        <Topbar
          user={user}
          onLogout={handleLogout}
        />
      )}
      {renderScreen()}
      {showContinueDialog && (
        <ContinueDialog
          rowsRemaining={rowsRemaining}
          isFinished={isProjectFinished}
          onContinue={() => {
            setShowContinueDialog(false);
            fetchNextTask(activeProject.id);
          }}
          onExit={() => {
            setShowContinueDialog(false);
            setActiveProject(null);
            fetchProjects();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components (could be moved to separate files for better organization)
// ---------------------------------------------------------------------------

function LoadingScreen() {
  return (
    <div className="loading-state">
      <div className="spinner"></div>
      <span>טוען נתונים…</span>
    </div>
  );
}

function Topbar({ user, onLogout }) {
  return (
    <div className="topbar">
      <div className="logo">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="3" y="3" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.9" />
          <rect x="13" y="3" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.5" />
          <rect x="3" y="13" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.5" />
          <rect x="13" y="13" width="8" height="8" rx="2" fill="#3fb950" opacity="0.8" />
        </svg>
        מערכת התיוג
      </div>
      <div className="user-badge">
        <span>מחובר כ: <strong>{user}</strong></span>
        <button className="btn btn-secondary" style={{ padding: '7px 16px', fontSize: '0.85rem' }} onClick={onLogout}>
          התנתקות
        </button>
      </div>
    </div>
  );
}

function LoginScreen({ onLogin, error }) {
  const [userName, setUserName] = useState('');

  return (
    <section className="screen active">
      <div style={{ textAlign: 'center', margin: '48px 0 36px' }}>
        <div style={{ fontSize: '3.5rem', marginBottom: '16px' }}>🏷️</div>
        <h1>מערכת התיוג הרב-מודלית</h1>
        <p className="subtitle">פלטפורמה לתיוג נתונים אקדמית ומקצועית</p>
      </div>
      <div className="card">
        <h2>כניסה למערכת</h2>
        <p className="subtitle">אנא הזן את שמך המלא כדי להתחיל בתהליך התיוג.</p>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="field-group">
          <label>שם משתמש</label>
          <input
            type="text"
            value={userName}
            onChange={(e) => setUserName(e.target.value)}
            placeholder='לדוגמה: פרופסור כהן'
            onKeyDown={(e) => e.key === 'Enter' && onLogin(userName)}
          />
        </div>
        <button className="btn btn-primary btn-full" onClick={() => onLogin(userName)}>
          כניסה למערכת
        </button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// DeleteConfirmDialog – shows when user clicks the trash icon
// ---------------------------------------------------------------------------

function DeleteConfirmDialog({ project, onCancel, onConfirm }) {
  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog-box" onClick={e => e.stopPropagation()} style={{ maxWidth: '460px', textAlign: 'right' }}>
        <div className="dialog-icon">🗑️</div>
        <h2>מחיקת פרויקט</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '8px', fontSize: '0.95rem', lineHeight: 1.6 }}>
          אתה עומד למחוק את הפרויקט <strong>{project.name}</strong>.
          <br />איזו רמת מחיקה תרצה?
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '20px' }}>
          <button
            className="btn btn-danger"
            style={{ width: '100%', justifyContent: 'flex-start', gap: '12px', padding: '14px 18px' }}
            onClick={() => onConfirm(true)}
          >
            <span style={{ fontSize: '1.2rem' }}>🗑️</span>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 700 }}>מחק הכל</div>
              <div style={{ fontSize: '0.78rem', opacity: 0.8, fontWeight: 400 }}>מוחק את הפרויקט + קובץ המקור + קובץ תוצאות (Master)</div>
            </div>
          </button>
          <button
            className="btn btn-secondary"
            style={{ width: '100%', justifyContent: 'flex-start', gap: '12px', padding: '14px 18px' }}
            onClick={() => onConfirm(false)}
          >
            <span style={{ fontSize: '1.2rem' }}>📌</span>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 700 }}>מחק רק את הפרויקט</div>
              <div style={{ fontSize: '0.78rem', opacity: 0.8, fontWeight: 400 }}>מסיר את הפרויקט מהמסך – הקבצים נשארים כמו שהם</div>
            </div>
          </button>
          <button className="btn btn-secondary" style={{ width: '100%' }} onClick={onCancel}>
            ביטול
          </button>
        </div>
      </div>
    </div>
  );
}

function ProjectsScreen({ projects, onSelect, onCreateNew, onEdit, onDelete, error }) {
  const [deleteTarget, setDeleteTarget] = React.useState(null);

  const handleDeleteConfirm = (deleteFiles) => {
    onDelete(deleteTarget.id, deleteFiles);
    setDeleteTarget(null);
  };

  return (
    <section className="screen active" style={{ width: '100%', maxWidth: '1100px' }}>
      {deleteTarget && (
        <DeleteConfirmDialog
          project={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={handleDeleteConfirm}
        />
      )}
      <div style={{ marginBottom: '28px' }}>
        <h1>בחר פרויקט למחקר</h1>
        <p className="subtitle">בחר באחד מהפרויקטים הפעילים או הקם פרויקט מחקרי חדש.</p>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="projects-grid">
        <div className="project-card new-project" onClick={onCreateNew}>
          <div className="new-icon">＋</div>
          <span>הקמת פרויקט חדש</span>
        </div>
        {projects.map((p) => {
          const hasError = !!p.init_error;
          const hasTasks = (p.rows_remaining || 0) > 0;
          // Block entry only if error AND no tasks loaded at all
          const isBlocked = p.is_finished || (hasError && !hasTasks);
          return (
          <div
            key={p.id}
            className={`project-card ${p.is_finished ? 'finished' : ''}`}
            onClick={() => !isBlocked && onSelect(p)}
            style={{
              position: 'relative',
              border: hasError ? '1px solid #ff4d4f' : '',
              cursor: isBlocked ? 'default' : 'pointer',
            }}
          >
            {/* Action buttons area */}
            <div style={{ position: 'absolute', top: '12px', left: '12px', display: 'flex', gap: '8px' }}>
              <button
                className="project-action-btn edit-btn"
                title="ערוך פרויקט"
                onClick={(e) => { e.stopPropagation(); onEdit(p); }}
              >
                ✏️
              </button>
              <button
                className="project-action-btn delete-btn"
                title="מחק פרויקט"
                onClick={(e) => { e.stopPropagation(); setDeleteTarget(p); }}
              >
                🗑️
              </button>
            </div>

            <h3>{p.name}</h3>
            <div className="project-meta">
              <span>חוקר אחראי: {p.owner}</span>
              {hasError && (
                <span style={{ color: '#ff4d4f', fontWeight: 'bold', marginTop: '4px', display: 'block' }}>
                  ⚠️ שגיאת גישה לקישור (פרטי / לא חוקי)
                </span>
              )}
              {!p.is_finished && (
                <span style={{ marginTop: hasError ? '2px' : undefined, display: hasError ? 'block' : undefined }}>
                  {hasTasks ? `משימות נותרות: ${p.rows_remaining}` : (hasError ? 'אין משימות זמינות' : 'המחקר הושלם')}
                </span>
              )}
              {p.is_finished && <span>המחקר הושלם</span>}
            </div>
            {!hasError && (
              <span className={`badge ${p.is_finished ? 'badge-done' : `badge-${p.workflow_type.toLowerCase()}`}`}>
                {p.is_finished ? '✓ הושלם' : `תהליך ${p.workflow_type}`}
              </span>
            )}
            {hasError && hasTasks && (
              <span className={`badge badge-${p.workflow_type.toLowerCase()}`}>
                {`תהליך ${p.workflow_type}`}
              </span>
            )}
          </div>
          );
        })}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Workflow Builder Helper – used inside NewProjectScreen
// ---------------------------------------------------------------------------

const FIELD_TYPES = [
  { value: 'input_text', label: 'שדה טקסט חופשי' },
  { value: 'textarea', label: 'תיבת טקסט (textarea)' },
  { value: 'button_group', label: 'כפתורי בחירה' },
  { value: 'select', label: 'רשימה נגללת' },
];

function WorkflowBuilder({ steps, onChange }) {
  // Stores raw comma-separated text while the user is typing,
  // so the comma character itself isn't immediately consumed by the parser.
  const [optionsTexts, setOptionsTexts] = useState({});

  const addStep = () => {
    onChange([...steps, { title: '', fields: [] }]);
  };

  const removeStep = (si) => {
    onChange(steps.filter((_, i) => i !== si));
  };

  const updateStep = (si, key, val) => {
    const updated = steps.map((s, i) => i === si ? { ...s, [key]: val } : s);
    onChange(updated);
  };

  const addField = (si) => {
    const updated = steps.map((s, i) =>
      i === si ? { ...s, fields: [...s.fields, { id: `field_${Date.now()}`, label: '', component: 'input_text', placeholder: '', options: [] }] } : s
    );
    onChange(updated);
  };

  const removeField = (si, fi) => {
    const updated = steps.map((s, i) =>
      i === si ? { ...s, fields: s.fields.filter((_, j) => j !== fi) } : s
    );
    onChange(updated);
  };

  const updateField = (si, fi, key, val) => {
    const updated = steps.map((s, i) =>
      i === si ? {
        ...s, fields: s.fields.map((f, j) => j === fi ? { ...f, [key]: val } : f)
      } : s
    );
    onChange(updated);
  };

  // While typing: store raw text locally (allows commas mid-sentence)
  const handleOptionsChange = (si, fi, val) => {
    setOptionsTexts(prev => ({ ...prev, [`${si}_${fi}`]: val }));
  };

  // On blur: parse raw text into array and push to real state
  const handleOptionsBlur = (si, fi) => {
    const key = `${si}_${fi}`;
    const raw = optionsTexts[key] ?? (steps[si]?.fields[fi]?.options || []).join(', ');
    const opts = raw.split(',').map(o => o.trim()).filter(Boolean);
    updateField(si, fi, 'options', opts);
    // Remove from local cache so value is now driven by real state
    setOptionsTexts(prev => { const c = { ...prev }; delete c[key]; return c; });
  };

  // Decide what value to show in the options input
  const getOptionsText = (si, fi, field) => {
    const key = `${si}_${fi}`;
    return key in optionsTexts ? optionsTexts[key] : (field.options || []).join(', ');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {steps.map((step, si) => (
        <div key={si} style={{
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '18px',
          background: 'var(--bg-secondary)',
          position: 'relative'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <span style={{ fontWeight: 600, color: 'var(--accent)', fontSize: '0.9rem' }}>שלב {si + 1}</span>
            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem', minWidth: 'auto' }} onClick={() => removeStep(si)}>
              ✕ הסר שלב
            </button>
          </div>
          <div className="field-group">
            <label>כותרת השלב</label>
            <input
              type="text"
              value={step.title}
              onChange={e => updateStep(si, 'title', e.target.value)}
              placeholder={`למשל: שלב ${si + 1} – זיהוי ישות`}
            />
          </div>

          {step.fields.map((field, fi) => (
            <div key={fi} style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              borderRadius: '10px',
              padding: '14px',
              marginBottom: '12px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>שדה {fi + 1}</span>
                <button className="btn btn-secondary" style={{ padding: '3px 8px', fontSize: '0.75rem', minWidth: 'auto' }} onClick={() => removeField(si, fi)}>
                  ✕
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div className="field-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.8rem' }}>שם השדה (תווית)</label>
                  <input
                    type="text"
                    value={field.label}
                    onChange={e => updateField(si, fi, 'label', e.target.value)}
                    placeholder="למשל: בחר ישות"
                  />
                </div>
                <div className="field-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.8rem' }}>סוג קלט</label>
                  <select value={field.component} onChange={e => updateField(si, fi, 'component', e.target.value)}>
                    {FIELD_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
              </div>
              {(field.component === 'input_text' || field.component === 'textarea') && (
                <div className="field-group" style={{ marginTop: '10px', marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem' }}>טקסט עזר (Placeholder)</label>
                  <input
                    type="text"
                    value={field.placeholder}
                    onChange={e => updateField(si, fi, 'placeholder', e.target.value)}
                    placeholder="למשל: בנק ישראל"
                  />
                </div>
              )}
              {(field.component === 'button_group' || field.component === 'select') && (
                <div className="field-group" style={{ marginTop: '10px', marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem' }}>אפשרויות (מופרדות בפסיק) – לחץ Tab או צא מהשדה לאישור</label>
                  <input
                    type="text"
                    value={getOptionsText(si, fi, field)}
                    onChange={e => handleOptionsChange(si, fi, e.target.value)}
                    onBlur={() => handleOptionsBlur(si, fi)}
                    placeholder="למשל: חיובי, שלילי, ניטרלי"
                  />
                  {/* Live preview of parsed options */}
                  {(steps[si]?.fields[fi]?.options?.length > 0) && (
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px' }}>
                      {steps[si].fields[fi].options.map((opt, oi) => (
                        <span key={oi} style={{
                          background: 'rgba(88,166,255,0.15)',
                          color: 'var(--accent)',
                          padding: '2px 10px',
                          borderRadius: '999px',
                          fontSize: '0.78rem',
                          fontWeight: 500
                        }}>{opt}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          <button className="btn btn-secondary" style={{ width: '100%', marginTop: '4px', fontSize: '0.85rem' }} onClick={() => addField(si)}>
            + הוסף שדה לשלב זה
          </button>
        </div>
      ))}
      <button className="btn btn-secondary" style={{ border: '2px dashed var(--border)', background: 'transparent' }} onClick={addStep}>
        + הוסף שלב חדש
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NewProjectScreen – now with full workflow builder
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Helper – human-readable label for a CSV source path or URL
// ---------------------------------------------------------------------------

function getSourceLabel(src) {
  const base = src.split('?')[0];
  const parts = base.split(/[/\\]/).filter(Boolean);
  const last = parts.length ? parts[parts.length - 1] : src;
  if (src.includes('drive.google.com') || src.includes('docs.google.com')) {
    return `Google Drive - ${last}`;
  }
  return last;
}

// ---------------------------------------------------------------------------
// ProjectFormScreen – handles both creating and editing projects
// ---------------------------------------------------------------------------

function ProjectFormScreen({ onSubmit, onBack, error, initialData = null, isEdit = false }) {
  const [name, setName] = useState(initialData?.name || '');
  const [workflowMode, setWorkflowMode] = useState(initialData?.custom_schema ? 'custom' : 'preset');
  const [workflow, setWorkflow] = useState(initialData?.workflow_type || 'A');
  const [contentType, setContentType] = useState(initialData?.custom_schema?.content_type || 'both');
  const [customSteps, setCustomSteps] = useState(initialData?.custom_schema?.steps || []);

  // Per-source errors from the backend (source_path -> error message)
  const sourceErrors = initialData?.source_errors || {};

  // CSV sources — support csv_sources (new array) or source_csv (legacy single string)
  const initialSources = initialData?.csv_sources ??
    (initialData?.source_csv ? [initialData.source_csv] : []);
  const [csvSources, setCsvSources] = useState(initialSources);
  const [sourceType, setSourceType] = useState('local');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [manualInput, setManualInput] = useState('');
  const [manualMsg, setManualMsg] = useState('');       // '' | success text | error text
  const [manualMsgType, setManualMsgType] = useState('success'); // 'success' | 'error'
  const [sourceLabels, setSourceLabels] = useState({});  // raw URL → display label

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    setUploadError('');
    // Track paths added in this batch so we catch intra-batch duplicates too
    const addedThisBatch = [];
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch('/api/upload-csv', {
          method: 'POST',
          credentials: 'include',
          body: formData,
        });
        const data = await res.json();
        if (res.ok) {
          if (csvSources.includes(data.path) || addedThisBatch.includes(data.path)) {
            setUploadError('המקור כבר משויך לפרויקט');
          } else {
            setCsvSources(prev => [...prev, data.path]);
            addedThisBatch.push(data.path);
          }
        } else {
          setUploadError(data.error || 'שגיאה בהעלאה');
        }
      } catch (err) {
        setUploadError('שגיאת רשת: ' + err.message);
      }
    }
    setUploading(false);
    e.target.value = '';
  };

  const removeSource = (idx) => {
    setCsvSources(prev => prev.filter((_, i) => i !== idx));
  };

  const addManualSource = () => {
    const trimmed = manualInput.trim();
    if (!trimmed) return;
    if (csvSources.includes(trimmed)) {
      setManualMsg('המקור כבר משויך לפרויקט');
      setManualMsgType('error');
      return;
    }
    setCsvSources(prev => [...prev, trimmed]);
    setManualInput('');

    let displayLabel = getSourceLabel(trimmed);
    if (sourceType === 'gdrive' || sourceType === 's3') {
      const name = window.prompt("שם הקובץ לתצוגה:", "");
      if (name && name.trim()) {
        const provider = sourceType === 'gdrive' ? "Google Drive" : "AWS S3";
        const label = provider + " - " + name.trim();
        setSourceLabels(prev => ({ ...prev, [trimmed]: label }));
        displayLabel = label;
      }
    }

    setManualMsg('קובץ הוסף בהצלחה: ' + displayLabel);
    setManualMsgType('success');
  };

  const handleSubmit = () => {
    const payload = {
      name,
      csv_sources: csvSources,
      owner: initialData?.owner,
    };

    if (workflowMode === 'custom') {
      payload.workflow_type = 'CUSTOM';
      payload.custom_schema = { steps: customSteps, content_type: contentType };
    } else {
      payload.workflow_type = workflow;
    }

    onSubmit(payload);
  };

  return (
    <section className="screen active">
      <div className="card" style={{ maxWidth: '720px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <button className="btn btn-secondary" style={{ padding: '8px 14px', minWidth: 'auto' }} onClick={onBack}>
            ← חזור
          </button>
          <h2 style={{ margin: 0 }}>{isEdit ? 'עריכת פרויקט' : 'הקמת פרויקט מחקרי חדש'}</h2>
        </div>
        {error && <div className="alert alert-error">{error}</div>}

        {/* Project name */}
        <div className="field-group">
          <label>שם הפרויקט</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="לדוגמה: מחקר זיהוי אובייקטים 2024"
          />
        </div>

        {/* CSV Sources */}
        <div className="field-group">
          <label>קובצי מקור (CSV)</label>

          {/* List of already-added sources */}
          {csvSources.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
              {csvSources.map((src, idx) => {
                const srcError = sourceErrors[src];
                return (
                <div key={idx} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: srcError ? 'rgba(255,77,79,0.08)' : 'rgba(63,185,80,0.08)',
                  border: srcError ? '1px solid rgba(255,77,79,0.4)' : '1px solid rgba(63,185,80,0.25)',
                  borderRadius: '8px',
                  fontSize: '0.88rem',
                }}>
                  <span style={{ color: srcError ? '#ff4d4f' : 'var(--accent-success)' }}>
                    {srcError ? '⚠️' : '✓'} {sourceLabels[src] || getSourceLabel(src)}
                    {srcError && (
                      <span style={{ display: 'block', fontSize: '0.78rem', opacity: 0.8, fontWeight: 400, marginTop: '2px' }}>
                        שגיאת גישה (פרטי / לא חוקי)
                      </span>
                    )}
                  </span>
                  <button
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: '1rem', lineHeight: 1, padding: '0 2px' }}
                    onClick={() => removeSource(idx)}
                    title="הסר קובץ"
                  >✕</button>
                </div>
                );
              })}
            </div>
          )}

          {/* Source type picker */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '12px' }}>
            {[
              { value: 'local', icon: '📁', label: 'מהמחשב' },
              { value: 'gdrive', icon: '☁️', label: 'Google Drive' },
              { value: 's3', icon: '🪣', label: 'AWS S3' },
            ].map(st => (
              <div
                key={st.value}
                className={`preset-option ${sourceType === st.value ? 'selected' : ''}`}
                style={{ flexDirection: 'column', justifyContent: 'center', textAlign: 'center', padding: '12px 8px', gap: '4px' }}
                onClick={() => { setSourceType(st.value); setManualInput(''); setUploadError(''); setManualMsg(''); }}
              >
                <span style={{ fontSize: '1.3rem' }}>{st.icon}</span>
                <strong style={{ fontSize: '0.83rem' }}>{st.label}</strong>
              </div>
            ))}
          </div>

          {/* Local upload */}
          {sourceType === 'local' && (
            <div>
              <label
                htmlFor="csv-upload"
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
                  padding: '16px', borderRadius: '10px',
                  border: '2px dashed var(--glass-border)',
                  cursor: uploading ? 'not-allowed' : 'pointer',
                  background: 'rgba(255,255,255,0.03)',
                  transition: 'border-color 0.2s',
                  color: 'var(--text-secondary)',
                  fontSize: '0.9rem',
                }}
              >
                {uploading
                  ? <><span className="spinner" /><span>מעלה...</span></>
                  : <><span>📂</span><span>לחץ לבחירת קובץ CSV (ניתן לבחור מרובים)</span></>}
              </label>
              <input
                id="csv-upload"
                type="file"
                accept=".csv"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileUpload}
                disabled={uploading}
              />
              {uploadError && (
                <p className="field-hint" style={{ color: 'var(--accent-danger)', marginTop: '6px' }}>{uploadError}</p>
              )}
            </div>
          )}

          {/* Google Drive */}
          {sourceType === 'gdrive' && (
            <div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={manualInput}
                  onChange={e => { setManualInput(e.target.value); setManualMsg(''); }}
                  onKeyDown={e => e.key === 'Enter' && addManualSource()}
                  placeholder="הדבק לינק שיתוף של Google Drive (קובץ CSV)"
                />
                <button className="btn btn-secondary" style={{ minWidth: 'auto', padding: '10px 16px' }} onClick={addManualSource}>הוסף</button>
              </div>
              {manualMsg && (
                <p className="field-hint" style={{ marginTop: '6px', color: manualMsgType === 'success' ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                  {manualMsg}
                </p>
              )}
              <p className="field-hint">וודא שהקובץ שיתוף ל׳כל מי שיש לו קישור׳ ושהוא בפורמט CSV</p>
            </div>
          )}

          {/* S3 */}
          {sourceType === 's3' && (
            <div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={manualInput}
                  onChange={e => { setManualInput(e.target.value); setManualMsg(''); }}
                  onKeyDown={e => e.key === 'Enter' && addManualSource()}
                  placeholder="למשל: s3://my-bucket/data/labels.csv"
                />
                <button className="btn btn-secondary" style={{ minWidth: 'auto', padding: '10px 16px' }} onClick={addManualSource}>הוסף</button>
              </div>
              {manualMsg && (
                <p className="field-hint" style={{ marginTop: '6px', color: manualMsgType === 'success' ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                  {manualMsg}
                </p>
              )}
              <p className="field-hint">הזן S3 URI מלא (s3://bucket/key) – ודא שלשרת יש הרשאות גישה</p>
            </div>
          )}
        </div>

        <hr className="divider" />

        {/* Workflow mode toggle */}
        <div className="field-group">
          <label>בחר סוג תהליך עבודה</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '8px' }}>
            <div
              className={`workflow-mode-card ${workflowMode === 'preset' ? 'selected' : ''}`}
              onClick={() => setWorkflowMode('preset')}
            >
              <div style={{ fontSize: '1.4rem', marginBottom: '6px' }}>📋</div>
              <strong>תהליך מוגדר מראש</strong>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
                בחר מתוך תהליכים A, B, C הקיימים במערכת
              </p>
            </div>
            <div
              className={`workflow-mode-card ${workflowMode === 'custom' ? 'selected' : ''}`}
              onClick={() => setWorkflowMode('custom')}
            >
              <div style={{ fontSize: '1.4rem', marginBottom: '6px' }}>🔧</div>
              <strong>בנה תהליך מותאם אישית</strong>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
                הגדר שלבים, שדות ואפשרויות לפי הצורך
              </p>
            </div>
          </div>
        </div>

        {/* Preset workflow selector */}
        {workflowMode === 'preset' && (
          <div className="field-group">
            <label>תהליך עבודה</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { value: 'A', label: 'א׳ – קשר תמונה-טקסט', desc: 'מתאים לניתוח הקשר בין תמונה לטקסט נלווה. מציג תמונה וטקסט, מבקש סיווג הקשר.', icon: '🖼️' },
                { value: 'B', label: 'ב׳ – ניתוח ישויות וסנטימנט', desc: 'תהליך מרובה שלבים: זיהוי ישות, קביעת נושא, וניתוח סנטימנט.', icon: '🔍' },
                { value: 'C', label: 'ג׳ – כתיבת כיתובים (Captions)', desc: 'הצגת תמונה וביקוש לכתיבת תיאור חופשי (Caption).', icon: '✍️' },
              ].map(opt => (
                <div
                  key={opt.value}
                  className={`preset-option ${workflow === opt.value ? 'selected' : ''}`}
                  onClick={() => setWorkflow(opt.value)}
                >
                  <span style={{ fontSize: '1.4rem' }}>{opt.icon}</span>
                  <div>
                    <strong>{opt.label}</strong>
                    <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{opt.desc}</p>
                  </div>
                  <div style={{ marginRight: 'auto', width: '18px', height: '18px', borderRadius: '50%', border: '2px solid var(--accent)', background: workflow === opt.value ? 'var(--accent)' : 'transparent', flexShrink: 0 }} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Custom workflow builder */}
        {workflowMode === 'custom' && (
          <>
            <div className="field-group">
              <label>סוג תוכן הנתונים</label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                {[
                  { value: 'image', label: '🖼️ תמונות בלבד' },
                  { value: 'text', label: '📝 טקסט בלבד' },
                  { value: 'both', label: '🖼️+📝 תמונה וטקסט' },
                ].map(ct => (
                  <div
                    key={ct.value}
                    className={`preset-option ${contentType === ct.value ? 'selected' : ''}`}
                    style={{ justifyContent: 'center', textAlign: 'center', padding: '12px', flexDirection: 'column', gap: '4px' }}
                    onClick={() => setContentType(ct.value)}
                  >
                    <strong style={{ fontSize: '0.85rem' }}>{ct.label}</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className="field-group">
              <label>שלבי תהליך העבודה</label>
              <WorkflowBuilder steps={customSteps} onChange={setCustomSteps} />
            </div>
          </>
        )}

        <hr className="divider" />
        <div className="btn-row">
          <button className="btn btn-secondary" onClick={onBack}>ביטול</button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            {isEdit ? 'שמור שינויים' : 'יצירת פרויקט'}
          </button>
        </div>
      </div>
    </section>
  );
}

function TaskScreen({ project, task, isFinished, onSubmit, onExit, error }) {
  const [config, setConfig] = useState(null);
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [imageLoaded, setImageLoaded] = useState(false);

  useEffect(() => {
    if (task) {
        setImageLoaded(false);
    }
  }, [task]);

  useEffect(() => {
    if (project && !isFinished) {
      async function fetchConfig() {
        setLoadingConfig(true);
        const { ok, data } = await api.getProjectConfig(project.id);
        if (ok) setConfig(data);
        setLoadingConfig(false);
      }
      fetchConfig();
    }
  }, [project, isFinished]);

  if (isFinished || !task) {
    return (
      <section className="screen active">
        <div className="card empty-state">
          <div className="big-icon">🎉</div>
          <h2>כל המשימות הושלמו</h2>
          <p className="subtitle">השלמת בהצלחה את כל משימות התיוג בפרויקט זה.</p>
          <button className="btn btn-secondary" onClick={onExit}>חזרה לרשימת הפרויקטים</button>
        </div>
      </section>
    );
  }

  return (
    <section className="screen active">
      <div className="card card-wide">
        <div className="task-header">
          <div>
            <h2>{project.name}</h2>
            <span className="info-chip">פרויקט מחקרי | תהליך {project.workflow_type}</span>
            {task?.source_csv && (
              <span className="info-chip" style={{ marginRight: '6px' }}>
                📄 {getSourceLabel(task.source_csv)}
              </span>
            )}
          </div>
          <button className="btn btn-secondary" style={{ padding: '8px 14px', minWidth: 'auto' }} onClick={onExit}>
            יציאה
          </button>
        </div>

        {task.has_image && (
          <div className="task-image-container" style={{ position: 'relative', minHeight: '200px' }}>
            {task.use_image_loading_bar && !imageLoaded && (
              <div 
                className="loading-state" 
                style={{
                  position: 'absolute', 
                  top: 0, 
                  left: 0, 
                  right: 0, 
                  bottom: 0, 
                  display: 'flex', 
                  justifyContent: 'center', 
                  alignItems: 'center', 
                  backgroundColor: 'var(--bg-primary)',
                  zIndex: 10,
                  borderRadius: '12px'
                }}
              >
                <div className="spinner"></div>
                <span style={{ marginTop: '12px', color: 'var(--text-secondary)' }}>טוען תמונה…</span>
              </div>
            )}
            <img 
              src={task.image_path} 
              alt="Task" 
              onLoad={() => setImageLoaded(true)}
              style={task.use_image_loading_bar && !imageLoaded ? { display: 'none' } : {}}
            />
          </div>
        )}

        {task.has_text && (
          <div className="task-text-box">{task.text_content}</div>
        )}

        {error && <div className="alert alert-error">{error}</div>}

        <div id="task-fields">
          {loadingConfig ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <span>טוען הגדרות תהליך...</span>
            </div>
          ) : config ? (
            <DynamicWorkflow
              key={task.row_id}
              config={config}
              onSubmit={onSubmit}
            />
          ) : (
            <div className="alert alert-error">שגיאה בטעינת הגדרות התהליך</div>
          )}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Dynamic Workflow Engine
// ---------------------------------------------------------------------------

/**
 * Renders any workflow dynamically based on the schema provided by the backend.
 * Handles multi-step navigation and field validation automatically.
 */
function DynamicWorkflow({ config, onSubmit }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [formData, setFormData] = useState({});

  if (!config || !config.steps) return null;

  const currentStep = config.steps[stepIndex];
  const isLastStep = stepIndex === config.steps.length - 1;

  const handleFieldChange = (fieldId, value) => {
    setFormData(prev => ({ ...prev, [fieldId]: value }));
  };

  // Ensure all fields in the current step are filled before proceeding
  const canGoNext = currentStep.fields.every(f => {
    const val = formData[f.id];
    return val !== undefined && val !== null && val.toString().trim() !== '';
  });

  const handleAction = () => {
    if (isLastStep) {
      onSubmit(formData);
    } else {
      setStepIndex(stepIndex + 1);
    }
  };

  return (
    <div className="dynamic-workflow">
      {/* Progress horizontal line for multi-step tasks */}
      {config.steps.length > 1 && (
        <div className="steps-indicator">
          {config.steps.map((_s, idx) => (
            <React.Fragment key={idx}>
              <div className={`step-dot ${stepIndex === idx ? 'active' : stepIndex > idx ? 'done' : ''}`}>
                {stepIndex > idx ? '✓' : idx + 1}
              </div>
              {idx < config.steps.length - 1 && <div className="step-line"></div>}
            </React.Fragment>
          ))}
        </div>
      )}

      <h2>{currentStep.title}</h2>

      <div className="step-fields">
        {currentStep.fields.map(field => (
          <DynamicField
            key={field.id}
            field={field}
            value={formData[field.id] || ''}
            onChange={val => handleFieldChange(field.id, val)}
          />
        ))}
      </div>

      <div className="btn-row">
        {stepIndex > 0 && (
          <button className="btn btn-secondary" onClick={() => setStepIndex(stepIndex - 1)}>
            חזור
          </button>
        )}
        <button
          className="btn btn-primary"
          onClick={handleAction}
          disabled={!canGoNext}
        >
          {isLastStep ? 'סיום ושליחה' : 'הבא ←'}
        </button>
      </div>
    </div>
  );
}

/**
 * A generic field renderer that picks the right component based on the schema.
 */
function DynamicField({ field, value, onChange }) {
  const renderInput = () => {
    switch (field.component) {
      case 'input_text':
        return (
          <input
            type="text"
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder={field.placeholder}
          />
        );
      case 'textarea':
        return (
          <textarea
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder={field.placeholder}
            rows={4}
          />
        );
      case 'button_group':
        return (
          <div className="choice-group">
            {field.options.map(opt => (
              <button
                key={opt}
                className={`choice-btn ${value === opt ? 'selected' : ''}`}
                onClick={() => onChange(opt)}
              >
                {opt}
              </button>
            ))}
          </div>
        );
      case 'select':
        return (
          <select value={value} onChange={e => onChange(e.target.value)}>
            <option value="">-- בחר אפשרות --</option>
            {field.options.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        );
      default:
        return <div className="alert alert-error">Unknown Component: {field.component}</div>;
    }
  };

  return (
    <div className="field-group">
      <label>{field.label}</label>
      {renderInput()}
    </div>
  );
}

function ContinueDialog({ rowsRemaining, isFinished, onContinue, onExit }) {
  return (
    <div className="dialog-overlay">
      <div className="dialog-box">
        <div className="dialog-icon">✅</div>
        <h2>התיוג נשלח בהצלחה</h2>
        <p>
          {isFinished
            ? 'השלמת את כל המשימות בפרויקט זה!'
            : `נותרו עוד ${rowsRemaining} משימות להשלמה.`}
        </p>
        <div className="btn-row" style={{ justifyContent: 'center', marginTop: 0 }}>
          {!isFinished && (
            <button className="btn btn-primary" onClick={onContinue}>
              המשך למשימה הבאה
            </button>
          )}
          <button className="btn btn-secondary" onClick={onExit}>
            חזרה לרשימה
          </button>
        </div>
      </div>
    </div>
  );
}
