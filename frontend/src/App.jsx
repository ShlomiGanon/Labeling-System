import React, { useState, useEffect } from 'react';
import * as api from './api/client';
import { useT } from './i18n/LanguageContext';
import { LanguageSwitcher } from './components/LanguageSwitcher';

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
  const { t } = useT();
  const [screen, setScreen] = useState('loading');
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [currentTask, setCurrentTask] = useState(null);
  const [showContinueDialog, setShowContinueDialog] = useState(false);
  const [rowsRemaining, setRowsRemaining] = useState(0);
  const [isProjectFinished, setIsProjectFinished] = useState(false);
  const [error, setError] = useState('');
  const [managerDashboard, setManagerDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState('');

  // ---------------------------------------------------------------------------
  // Login & Session logic
  // ---------------------------------------------------------------------------

  useEffect(() => {
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
      setError(data.error || t('errors.loginFailed'));
    }
  };

  const handleLogout = async () => {
    await api.logout();
    setUser(null);
    setScreen('login');
  };

  const handleGoToDashboard = async () => {
    setScreen('loading');
    setDashboardError('');
    const { ok, data } = await api.getManagerDashboard();
    if (ok) {
      setManagerDashboard(data);
    } else {
      setDashboardError(data.error || t('manager.loadFailed'));
      setManagerDashboard(null);
    }
    setScreen('manager');
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
      setError(t('errors.loadProjectsFailed'));
      setScreen('projects');
    }
  };

  const handleCreateProject = async (projectData) => {
    setError('');
    const { ok, data } = await api.createProject(projectData);
    if (ok) {
      fetchProjects();
    } else {
      setError(data.error || t('errors.createProjectFailed'));
    }
  };

  const handleUpdateProject = async (projectId, projectData) => {
    setError('');
    const { ok, data } = await api.updateProject(projectId, projectData);
    if (ok) {
      fetchProjects();
    } else {
      setError(data.error || t('errors.updateProjectFailed'));
    }
  };

  const handleDeleteProject = async (projectId, deleteFiles) => {
    const { ok, data } = await api.deleteProject(projectId, deleteFiles);
    if (ok) {
      setProjects(prev => prev.filter(p => p.id !== projectId));
    } else {
      setError(data.error || t('errors.deleteProjectFailed'));
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
      setError(data.error || t('errors.fetchTaskFailed'));
      setScreen('projects');
    }
  };

  const handleSubmitLabel = async (payload) => {
    setError('');
    const fullPayload = { ...payload, row_id: currentTask.row_id };
    const { ok, data } = await api.submitLabel(activeProject.id, fullPayload);
    if (ok) {
      setRowsRemaining(data.rows_remaining);
      setIsProjectFinished(data.is_finished);
      setShowContinueDialog(true);
    } else {
      setError(data.error || t('errors.submitLabelFailed'));
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
      case 'manager':
        return (
          <ManagerDashboard
            dashboardData={managerDashboard}
            error={dashboardError}
            onBack={fetchProjects}
          />
        );
      default:
        return <div>Unknown screen</div>;
    }
  };

  return (
    <div className="app-wrapper">
      {user
        ? <Topbar user={user} onLogout={handleLogout} onDashboard={handleGoToDashboard} />
        : <div className="lang-bar"><LanguageSwitcher /></div>
      }
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
  const { t } = useT();
  return (
    <div className="loading-state">
      <div className="spinner"></div>
      <span>{t('loading.data')}</span>
    </div>
  );
}

function Topbar({ user, onLogout, onDashboard }) {
  const { t } = useT();
  return (
    <div className="topbar">
      <div className="logo">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="3" y="3" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.9" />
          <rect x="13" y="3" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.5" />
          <rect x="3" y="13" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.5" />
          <rect x="13" y="13" width="8" height="8" rx="2" fill="#3fb950" opacity="0.8" />
        </svg>
        {t('app.name')}
      </div>
      <div className="topbar-end">
        <LanguageSwitcher />
        <div className="user-badge">
          <span>{t('topbar.connectedAs')} <strong>{user}</strong></span>
          <button
            className="btn btn-secondary"
            style={{ padding: '7px 16px', fontSize: '0.85rem' }}
            onClick={onDashboard}
          >
            {t('manager.myDashboard')}
          </button>
          <button
            className="btn btn-secondary"
            style={{ padding: '7px 16px', fontSize: '0.85rem' }}
            onClick={onLogout}
          >
            {t('topbar.logout')}
          </button>
        </div>
      </div>
    </div>
  );
}

function LoginScreen({ onLogin, error }) {
  const { t } = useT();
  const [userName, setUserName] = useState('');

  return (
    <section className="screen active">
      <div style={{ textAlign: 'center', margin: '48px 0 36px' }}>
        <div style={{ fontSize: '3.5rem', marginBottom: '16px' }}>🏷️</div>
        <h1>{t('login.title')}</h1>
        <p className="subtitle">{t('login.subtitle')}</p>
      </div>
      <div className="card">
        <h2>{t('login.cardTitle')}</h2>
        <p className="subtitle">{t('login.cardSubtitle')}</p>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="field-group">
          <label>{t('login.usernameLabel')}</label>
          <input
            type="text"
            value={userName}
            onChange={(e) => setUserName(e.target.value)}
            placeholder={t('login.usernamePlaceholder')}
            onKeyDown={(e) => e.key === 'Enter' && onLogin(userName)}
          />
        </div>
        <button className="btn btn-primary btn-full" onClick={() => onLogin(userName)}>
          {t('login.submitBtn')}
        </button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// DeleteConfirmDialog – shows when user clicks the trash icon
// ---------------------------------------------------------------------------

function DeleteConfirmDialog({ project, onCancel, onConfirm }) {
  const { t } = useT();
  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog-box" onClick={e => e.stopPropagation()} style={{ maxWidth: '460px', textAlign: 'start' }}>
        <div className="dialog-icon">🗑️</div>
        <h2>{t('delete.title')}</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '8px', fontSize: '0.95rem', lineHeight: 1.6 }}>
          {t('delete.description')} <strong>{project.name}</strong>.
          <br />{t('delete.question')}
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '20px' }}>
          <button
            className="btn btn-danger"
            style={{ width: '100%', justifyContent: 'flex-start', gap: '12px', padding: '14px 18px' }}
            onClick={() => onConfirm(true)}
          >
            <span style={{ fontSize: '1.2rem' }}>🗑️</span>
            <div style={{ textAlign: 'start' }}>
              <div style={{ fontWeight: 700 }}>{t('delete.deleteAll')}</div>
              <div style={{ fontSize: '0.78rem', opacity: 0.8, fontWeight: 400 }}>{t('delete.deleteAllDesc')}</div>
            </div>
          </button>
          <button
            className="btn btn-secondary"
            style={{ width: '100%', justifyContent: 'flex-start', gap: '12px', padding: '14px 18px' }}
            onClick={() => onConfirm(false)}
          >
            <span style={{ fontSize: '1.2rem' }}>📌</span>
            <div style={{ textAlign: 'start' }}>
              <div style={{ fontWeight: 700 }}>{t('delete.deleteProject')}</div>
              <div style={{ fontSize: '0.78rem', opacity: 0.8, fontWeight: 400 }}>{t('delete.deleteProjectDesc')}</div>
            </div>
          </button>
          <button className="btn btn-secondary" style={{ width: '100%' }} onClick={onCancel}>
            {t('delete.cancel')}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProjectsScreen({ projects, onSelect, onCreateNew, onEdit, onDelete, error }) {
  const { t } = useT();
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
        <h1>{t('projects.title')}</h1>
        <p className="subtitle">{t('projects.subtitle')}</p>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="projects-grid">
        <div className="project-card new-project" onClick={onCreateNew}>
          <div className="new-icon">＋</div>
          <span>{t('projects.newProject')}</span>
        </div>
        {projects.map((p) => {
          const hasError = !!p.init_error;
          const hasTasks = (p.rows_remaining || 0) > 0;
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
              <div style={{ position: 'absolute', top: '12px', insetInlineEnd: '12px', display: 'flex', gap: '8px' }}>
                <button
                  className="project-action-btn edit-btn"
                  title={t('projects.editTitle')}
                  onClick={(e) => { e.stopPropagation(); onEdit(p); }}
                >
                  ✏️
                </button>
                <button
                  className="project-action-btn delete-btn"
                  title={t('projects.deleteTitle')}
                  onClick={(e) => { e.stopPropagation(); setDeleteTarget(p); }}
                >
                  🗑️
                </button>
              </div>

              <h3>{p.name}</h3>
              <div className="project-meta">
                <span>{t('projects.researcher')} {p.owner}</span>
                {hasError && (
                  <span style={{ color: '#ff4d4f', fontWeight: 'bold', marginTop: '4px', display: 'block' }}>
                    ⚠️ {getProjectErrorLabel(p, t)}
                  </span>
                )}
                {!p.is_finished && (
                  <span style={{ marginTop: hasError ? '2px' : undefined, display: hasError ? 'block' : undefined }}>
                    {hasTasks
                      ? t('projects.tasksRemaining', { count: p.rows_remaining })
                      : (hasError ? t('projects.noTasksAvailable') : t('projects.completed'))}
                  </span>
                )}
                {p.is_finished && <span>{t('projects.completed')}</span>}
              </div>
              {!hasError && (
                <span className={`badge ${p.is_finished ? 'badge-done' : `badge-${p.workflow_type.toLowerCase()}`}`}>
                  {p.is_finished ? t('projects.badgeDone') : t('projects.badgeWorkflow', { type: p.workflow_type })}
                </span>
              )}
              {hasError && hasTasks && (
                <span className={`badge badge-${p.workflow_type.toLowerCase()}`}>
                  {t('projects.badgeWorkflow', { type: p.workflow_type })}
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

function WorkflowBuilder({ steps, onChange }) {
  const { t } = useT();

  const FIELD_TYPES = [
    { value: 'input_text', label: t('workflow.typeInputText') },
    { value: 'textarea', label: t('workflow.typeTextarea') },
    { value: 'button_group', label: t('workflow.typeButtonGroup') },
    { value: 'select', label: t('workflow.typeSelect') },
  ];

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

  const handleOptionsChange = (si, fi, val) => {
    setOptionsTexts(prev => ({ ...prev, [`${si}_${fi}`]: val }));
  };

  const handleOptionsBlur = (si, fi) => {
    const key = `${si}_${fi}`;
    const raw = optionsTexts[key] ?? (steps[si]?.fields[fi]?.options || []).join(', ');
    const opts = raw.split(',').map(o => o.trim()).filter(Boolean);
    updateField(si, fi, 'options', opts);
    setOptionsTexts(prev => { const c = { ...prev }; delete c[key]; return c; });
  };

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
            <span style={{ fontWeight: 600, color: 'var(--accent)', fontSize: '0.9rem' }}>
              {t('workflow.step', { n: si + 1 })}
            </span>
            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem', minWidth: 'auto' }} onClick={() => removeStep(si)}>
              {t('workflow.removeStep')}
            </button>
          </div>
          <div className="field-group">
            <label>{t('workflow.stepTitle')}</label>
            <input
              type="text"
              value={step.title}
              onChange={e => updateStep(si, 'title', e.target.value)}
              placeholder={t('workflow.stepTitlePlaceholder', { n: si + 1 })}
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
                <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  {t('workflow.field', { n: fi + 1 })}
                </span>
                <button className="btn btn-secondary" style={{ padding: '3px 8px', fontSize: '0.75rem', minWidth: 'auto' }} onClick={() => removeField(si, fi)}>
                  ✕
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div className="field-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.8rem' }}>{t('workflow.fieldLabel')}</label>
                  <input
                    type="text"
                    value={field.label}
                    onChange={e => updateField(si, fi, 'label', e.target.value)}
                    placeholder={t('workflow.fieldLabelPlaceholder')}
                  />
                </div>
                <div className="field-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.8rem' }}>{t('workflow.fieldType')}</label>
                  <select value={field.component} onChange={e => updateField(si, fi, 'component', e.target.value)}>
                    {FIELD_TYPES.map(ft => <option key={ft.value} value={ft.value}>{ft.label}</option>)}
                  </select>
                </div>
              </div>
              {(field.component === 'input_text' || field.component === 'textarea') && (
                <div className="field-group" style={{ marginTop: '10px', marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem' }}>{t('workflow.placeholder')}</label>
                  <input
                    type="text"
                    value={field.placeholder}
                    onChange={e => updateField(si, fi, 'placeholder', e.target.value)}
                    placeholder={t('workflow.placeholderExample')}
                  />
                </div>
              )}
              {(field.component === 'button_group' || field.component === 'select') && (
                <div className="field-group" style={{ marginTop: '10px', marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem' }}>{t('workflow.options')}</label>
                  <input
                    type="text"
                    value={getOptionsText(si, fi, field)}
                    onChange={e => handleOptionsChange(si, fi, e.target.value)}
                    onBlur={() => handleOptionsBlur(si, fi)}
                    placeholder={t('workflow.optionsPlaceholder')}
                  />
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
            {t('workflow.addField')}
          </button>
        </div>
      ))}
      <button className="btn btn-secondary" style={{ border: '2px dashed var(--border)', background: 'transparent' }} onClick={addStep}>
        {t('workflow.addStep')}
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

function getSourceErrorLabel(src, errorMessage, t) {
  if (!errorMessage) return '';
  if (src.includes('drive.google.com') || src.includes('docs.google.com')) {
    return t('errors.sourceGdrive');
  }
  if (errorMessage.includes('File not found') || errorMessage.includes('Source CSV not found')) {
    return t('errors.sourceLocal');
  }
  return t('errors.sourceGeneral');
}

function getProjectErrorLabel(project, t) {
  const sourceErrors = project?.source_errors || {};
  const sourceEntries = Object.entries(sourceErrors);
  if (!sourceEntries.length) {
    return t('errors.projectSourceGeneral');
  }
  const hasRemoteError = sourceEntries.some(([src]) => src.includes('drive.google.com') || src.includes('docs.google.com'));
  const hasLocalError = sourceEntries.some(([, message]) =>
    message.includes('File not found') || message.includes('Source CSV not found')
  );
  if (hasLocalError && !hasRemoteError) {
    return t('errors.projectSourceLocal');
  }
  if (hasRemoteError && !hasLocalError) {
    return t('errors.projectSourceGdrive');
  }
  return t('errors.projectSourceMixed');
}

function getProjectSourceDisplayName(project, sourcePath) {
  if (!sourcePath) return '';
  return project?.source_labels?.[sourcePath] || getSourceLabel(sourcePath);
}

// ---------------------------------------------------------------------------
// ProjectFormScreen – handles both creating and editing projects
// ---------------------------------------------------------------------------

function ProjectFormScreen({ onSubmit, onBack, error, initialData = null, isEdit = false }) {
  const { t } = useT();
  const [name, setName] = useState(initialData?.name || '');
  const [workflowMode, setWorkflowMode] = useState(initialData?.custom_schema ? 'custom' : 'preset');
  const [workflow, setWorkflow] = useState(initialData?.workflow_type || 'A');
  const [contentType, setContentType] = useState(initialData?.custom_schema?.content_type || 'both');
  const [customSteps, setCustomSteps] = useState(initialData?.custom_schema?.steps || []);

  const sourceErrors = initialData?.source_errors || {};

  const initialSources = initialData?.csv_sources ??
    (initialData?.source_csv ? [initialData.source_csv] : []);
  const [csvSources, setCsvSources] = useState(initialSources);
  const [sourceType, setSourceType] = useState('local');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [manualInput, setManualInput] = useState('');
  const [manualMsg, setManualMsg] = useState('');
  const [manualMsgType, setManualMsgType] = useState('success');
  const [sourceLabels, setSourceLabels] = useState(initialData?.source_labels || {});

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    setUploadError('');
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
            setUploadError(t('form.duplicateSource'));
          } else {
            setCsvSources(prev => [...prev, data.path]);
            addedThisBatch.push(data.path);
          }
        } else {
          setUploadError(data.error || t('errors.uploadFailed'));
        }
      } catch (err) {
        setUploadError(t('errors.networkError') + ' ' + err.message);
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
      setManualMsg(t('form.duplicateSource'));
      setManualMsgType('error');
      return;
    }
    setCsvSources(prev => [...prev, trimmed]);
    setManualInput('');

    let displayLabel = getSourceLabel(trimmed);
    if (sourceType === 'gdrive' || sourceType === 's3') {
      const inputName = window.prompt(t('form.sourceNamePrompt'), '');
      if (inputName && inputName.trim()) {
        const provider = sourceType === 'gdrive' ? 'Google Drive' : 'AWS S3';
        const label = provider + ' - ' + inputName.trim();
        setSourceLabels(prev => ({ ...prev, [trimmed]: label }));
        displayLabel = label;
      }
    }

    setManualMsg(t('form.sourceAdded') + ' ' + displayLabel);
    setManualMsgType('success');
  };

  const handleSubmit = () => {
    const payload = {
      name,
      csv_sources: csvSources,
      source_labels: sourceLabels,
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
            {t('form.back')}
          </button>
          <h2 style={{ margin: 0 }}>{isEdit ? t('form.editTitle') : t('form.newTitle')}</h2>
        </div>
        {error && <div className="alert alert-error">{error}</div>}

        {/* Project name */}
        <div className="field-group">
          <label>{t('form.projectName')}</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder={t('form.projectNamePlaceholder')}
          />
        </div>

        {/* CSV Sources */}
        <div className="field-group">
          <label>{t('form.csvSources')}</label>

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
                          {getSourceErrorLabel(src, srcError, t)}
                        </span>
                      )}
                    </span>
                    <button
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: '1rem', lineHeight: 1, padding: '0 2px' }}
                      onClick={() => removeSource(idx)}
                      title={t('form.removeFile')}
                    >✕</button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Source type picker */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '12px' }}>
            {[
              { value: 'local', icon: '📁', label: t('form.sourceLocal') },
              { value: 'gdrive', icon: '☁️', label: t('form.sourceGdrive') },
              { value: 's3', icon: '🪣', label: t('form.sourceS3') },
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
                  ? <><span className="spinner" /><span>{t('form.uploading')}</span></>
                  : <><span>📂</span><span>{t('form.uploadClick')}</span></>}
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
                  placeholder={t('form.gdrivePlaceholder')}
                />
                <button className="btn btn-secondary" style={{ minWidth: 'auto', padding: '10px 16px' }} onClick={addManualSource}>
                  {t('form.add')}
                </button>
              </div>
              {manualMsg && (
                <p className="field-hint" style={{ marginTop: '6px', color: manualMsgType === 'success' ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                  {manualMsg}
                </p>
              )}
              <p className="field-hint">{t('form.gdriveHint')}</p>
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
                  placeholder={t('form.s3Placeholder')}
                />
                <button className="btn btn-secondary" style={{ minWidth: 'auto', padding: '10px 16px' }} onClick={addManualSource}>
                  {t('form.add')}
                </button>
              </div>
              {manualMsg && (
                <p className="field-hint" style={{ marginTop: '6px', color: manualMsgType === 'success' ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                  {manualMsg}
                </p>
              )}
              <p className="field-hint">{t('form.s3Hint')}</p>
            </div>
          )}
        </div>

        <hr className="divider" />

        {/* Workflow mode toggle */}
        <div className="field-group">
          <label>{t('form.workflowLabel')}</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '8px' }}>
            <div
              className={`workflow-mode-card ${workflowMode === 'preset' ? 'selected' : ''}`}
              onClick={() => setWorkflowMode('preset')}
            >
              <div style={{ fontSize: '1.4rem', marginBottom: '6px' }}>📋</div>
              <strong>{t('form.presetTitle')}</strong>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
                {t('form.presetDesc')}
              </p>
            </div>
            <div
              className={`workflow-mode-card ${workflowMode === 'custom' ? 'selected' : ''}`}
              onClick={() => setWorkflowMode('custom')}
            >
              <div style={{ fontSize: '1.4rem', marginBottom: '6px' }}>🔧</div>
              <strong>{t('form.customTitle')}</strong>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
                {t('form.customDesc')}
              </p>
            </div>
          </div>
        </div>

        {/* Preset workflow selector */}
        {workflowMode === 'preset' && (
          <div className="field-group">
            <label>{t('form.workflowType')}</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { value: 'A', labelKey: 'form.workflowA', descKey: 'form.workflowADesc', icon: '🖼️' },
                { value: 'B', labelKey: 'form.workflowB', descKey: 'form.workflowBDesc', icon: '🔍' },
                { value: 'C', labelKey: 'form.workflowC', descKey: 'form.workflowCDesc', icon: '✍️' },
              ].map(opt => (
                <div
                  key={opt.value}
                  className={`preset-option ${workflow === opt.value ? 'selected' : ''}`}
                  onClick={() => setWorkflow(opt.value)}
                >
                  <span style={{ fontSize: '1.4rem' }}>{opt.icon}</span>
                  <div>
                    <strong>{t(opt.labelKey)}</strong>
                    <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{t(opt.descKey)}</p>
                  </div>
                  <div style={{ marginInlineStart: 'auto', width: '18px', height: '18px', borderRadius: '50%', border: '2px solid var(--accent)', background: workflow === opt.value ? 'var(--accent)' : 'transparent', flexShrink: 0 }} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Custom workflow builder */}
        {workflowMode === 'custom' && (
          <>
            <div className="field-group">
              <label>{t('form.contentType')}</label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                {[
                  { value: 'image', labelKey: 'form.contentImage' },
                  { value: 'text', labelKey: 'form.contentText' },
                  { value: 'both', labelKey: 'form.contentBoth' },
                ].map(ct => (
                  <div
                    key={ct.value}
                    className={`preset-option ${contentType === ct.value ? 'selected' : ''}`}
                    style={{ justifyContent: 'center', textAlign: 'center', padding: '12px', flexDirection: 'column', gap: '4px' }}
                    onClick={() => setContentType(ct.value)}
                  >
                    <strong style={{ fontSize: '0.85rem' }}>{t(ct.labelKey)}</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className="field-group">
              <label>{t('form.workflowSteps')}</label>
              <WorkflowBuilder steps={customSteps} onChange={setCustomSteps} />
            </div>
          </>
        )}

        <hr className="divider" />
        <div className="btn-row">
          <button className="btn btn-secondary" onClick={onBack}>{t('form.cancel')}</button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            {isEdit ? t('form.save') : t('form.create')}
          </button>
        </div>
      </div>
    </section>
  );
}

function TaskScreen({ project, task, isFinished, onSubmit, onExit, error }) {
  const { t } = useT();
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
          <h2>{t('task.allDone')}</h2>
          <p className="subtitle">{t('task.allDoneSubtitle')}</p>
          <button className="btn btn-secondary" onClick={onExit}>{t('task.backToProjects')}</button>
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
            <span className="info-chip">
              {t('task.projectChip', { type: project.workflow_type })}
            </span>
            {task?.source_csv && (
              <span className="info-chip" style={{ marginInlineStart: '6px' }}>
                📄 {getProjectSourceDisplayName(project, task.source_csv)}
              </span>
            )}
          </div>
          <button className="btn btn-secondary" style={{ padding: '8px 14px', minWidth: 'auto' }} onClick={onExit}>
            {t('task.exit')}
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
                <span style={{ marginTop: '12px', color: 'var(--text-secondary)' }}>{t('loading.image')}</span>
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
          <div className="task-text-box" dir="auto">{task.text_content}</div>
        )}

        {error && <div className="alert alert-error">{error}</div>}

        <div id="task-fields">
          {loadingConfig ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <span>{t('loading.workflow')}</span>
            </div>
          ) : config ? (
            <DynamicWorkflow
              key={task.row_id}
              config={config}
              onSubmit={onSubmit}
            />
          ) : (
            <div className="alert alert-error">{t('task.errorWorkflow')}</div>
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
  const { t } = useT();
  const [stepIndex, setStepIndex] = useState(0);
  const [formData, setFormData] = useState({});

  if (!config || !config.steps) return null;

  const currentStep = config.steps[stepIndex];
  const isLastStep = stepIndex === config.steps.length - 1;

  const handleFieldChange = (fieldId, value) => {
    setFormData(prev => ({ ...prev, [fieldId]: value }));
  };

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
            {t('task.back')}
          </button>
        )}
        <button
          className="btn btn-primary"
          onClick={handleAction}
          disabled={!canGoNext}
        >
          {isLastStep ? t('task.submit') : t('task.next')}
        </button>
      </div>
    </div>
  );
}

/**
 * A generic field renderer that picks the right component based on the schema.
 */
function DynamicField({ field, value, onChange }) {
  const { t } = useT();

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
            <option value="">{t('task.selectOption')}</option>
            {field.options.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        );
      default:
        return <div className="alert alert-error">{t('errors.unknownComponent')} {field.component}</div>;
    }
  };

  return (
    <div className="field-group">
      <label>{field.label}</label>
      {renderInput()}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ManagerDashboard – project overview + master CSV downloads for the owner
// ---------------------------------------------------------------------------

function ManagerDashboard({ dashboardData, error, onBack }) {
  const { t } = useT();
  const [downloadError, setDownloadError] = useState('');
  const [downloadingKey, setDownloadingKey] = useState(null);

  const stats = dashboardData?.stats || {};
  const projects = dashboardData?.projects || [];

  const handleDownload = async (projectId, source, filename) => {
    const key = `${projectId}__${source ?? 'main'}`;
    setDownloadingKey(key);
    setDownloadError('');
    const result = await api.downloadMasterFile(projectId, source);
    setDownloadingKey(null);
    if (!result.ok) {
      setDownloadError(t('manager.downloadError', { msg: result.error }));
      return;
    }
    const blobUrl = URL.createObjectURL(result.blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = result.filename || filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(blobUrl);
  };

  const STAT_CARDS = [
    { label: t('manager.stats.totalProjects'), value: stats.total ?? 0 },
    { label: t('manager.stats.active'),        value: stats.active ?? 0 },
    { label: t('manager.stats.completed'),     value: stats.completed ?? 0 },
    { label: t('manager.stats.rowsRemaining'), value: stats.rows_remaining ?? 0 },
  ];

  return (
    <section className="screen active" style={{ width: '100%', maxWidth: '900px' }}>
      <button
        className="btn btn-secondary"
        style={{ marginBottom: '20px', fontSize: '0.9rem' }}
        onClick={onBack}
      >
        {t('manager.backToProjects')}
      </button>

      <div style={{ marginBottom: '24px' }}>
        <h1>{t('manager.dashboardTitle')}</h1>
        <p className="subtitle">{t('manager.dashboardSubtitle')}</p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {downloadError && (
        <div className="alert alert-error" style={{ marginBottom: '16px' }}>
          {downloadError}
        </div>
      )}

      {/* Stats bar */}
      {dashboardData && (
        <div style={{ display: 'flex', gap: '14px', marginBottom: '28px', flexWrap: 'wrap' }}>
          {STAT_CARDS.map(({ label, value }) => (
            <div
              key={label}
              className="card"
              style={{ flex: '1 1 140px', textAlign: 'center', padding: '18px 12px' }}
            >
              <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent)', lineHeight: 1 }}>
                {value}
              </div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Per-project rows */}
      {dashboardData && projects.length === 0 && (
        <p style={{ color: 'var(--text-secondary)' }}>{t('manager.noProjects')}</p>
      )}

      {dashboardData && projects.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {projects.map((p) => (
            <div key={p.id} className="card" style={{ padding: '18px 20px' }}>
              {/* Project header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem' }}>{p.name}</h3>
                  <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {p.is_finished
                      ? t('projects.completed')
                      : p.rows_remaining > 0
                        ? t('projects.tasksRemaining', { count: p.rows_remaining })
                        : t('projects.noTasksAvailable')}
                  </div>
                </div>
                <span
                  className={`badge ${p.is_finished
                    ? 'badge-done'
                    : `badge-${(p.workflow_type || '').toLowerCase()}`}`}
                >
                  {p.is_finished
                    ? t('projects.badgeDone')
                    : t('projects.badgeWorkflow', { type: p.workflow_type })}
                </span>
              </div>

              {/* Download buttons */}
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                {t('manager.downloadFiles')}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {(p.downloadable_files || []).map((file, idx) => {
                  const key = `${p.id}__${file.source ?? 'main'}`;
                  const isLoading = downloadingKey === key;
                  return file.exists ? (
                    <button
                      key={idx}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.82rem', padding: '6px 14px' }}
                      onClick={() => handleDownload(p.id, file.source, file.label)}
                      disabled={isLoading}
                      title={file.label}
                    >
                      {isLoading ? '…' : '↓'} {file.label}
                    </button>
                  ) : (
                    <span
                      key={idx}
                      title={file.label}
                      style={{
                        fontSize: '0.82rem',
                        color: 'var(--text-muted)',
                        padding: '6px 14px',
                        border: '1px solid var(--border)',
                        borderRadius: '6px',
                        display: 'inline-block',
                        opacity: 0.6,
                      }}
                    >
                      {file.label} ({t('manager.noMasterYet')})
                    </span>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ContinueDialog({ rowsRemaining, isFinished, onContinue, onExit }) {
  const { t } = useT();
  return (
    <div className="dialog-overlay">
      <div className="dialog-box">
        <div className="dialog-icon">✅</div>
        <h2>{t('dialog.successTitle')}</h2>
        <p>
          {isFinished
            ? t('dialog.allDone')
            : t('dialog.remaining', { count: rowsRemaining })}
        </p>
        <div className="btn-row" style={{ justifyContent: 'center', marginTop: 0 }}>
          {!isFinished && (
            <button className="btn btn-primary" onClick={onContinue}>
              {t('dialog.continueBtn')}
            </button>
          )}
          <button className="btn btn-secondary" onClick={onExit}>
            {t('dialog.backToList')}
          </button>
        </div>
      </div>
    </div>
  );
}
