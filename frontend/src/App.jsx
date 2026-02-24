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
            error={error}
          />
        );
      case 'new-project':
        return (
          <NewProjectScreen
            onSubmit={handleCreateProject}
            onBack={() => setScreen('projects')}
            error={error}
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
          <rect x="3" y="3" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.9"/>
          <rect x="13" y="3" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.5"/>
          <rect x="3" y="13" width="8" height="8" rx="2" fill="#58a6ff" opacity="0.5"/>
          <rect x="13" y="13" width="8" height="8" rx="2" fill="#3fb950" opacity="0.8"/>
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

function ProjectsScreen({ projects, onSelect, onCreateNew, error }) {
  return (
    <section className="screen active" style={{ width: '100%', maxWidth: '1100px' }}>
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
        {projects.map((p) => (
          <div
            key={p.id}
            className={`project-card ${p.is_finished ? 'finished' : ''}`}
            onClick={() => !p.is_finished && onSelect(p)}
          >
            <h3>{p.name}</h3>
            <div className="project-meta">
              <span>חוקר אחראי: {p.owner}</span>
              <span>{p.is_finished ? 'המחקר הושלם' : `משימות נותרות: ${p.rows_remaining}`}</span>
            </div>
            <span className={`badge ${p.is_finished ? 'badge-done' : `badge-${p.workflow_type.toLowerCase()}`}`}>
              {p.is_finished ? '✓ הושלם' : `תהליך ${p.workflow_type}`}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function NewProjectScreen({ onSubmit, onBack, error }) {
  const [name, setName] = useState('');
  const [workflow, setWorkflow] = useState('A');
  const [source, setSource] = useState('');

  return (
    <section className="screen active">
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <button className="btn btn-secondary" style={{ padding: '8px 14px', minWidth: 'auto' }} onClick={onBack}>
            ← חזור
          </button>
          <h2 style={{ margin: 0 }}>הקמת פרויקט מחקרי חדש</h2>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="field-group">
          <label>שם הפרויקט</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder='לדוגמה: מחקר זיהוי אובייקטים 2024' />
        </div>
        <div className="field-group">
          <label>סוג תהליך עבודה</label>
          <select value={workflow} onChange={(e) => setWorkflow(e.target.value)}>
            <option value="A">א׳ – קשר תמונה-טקסט</option>
            <option value="B">ב׳ – ניתוח ישויות וסנטימנט</option>
            <option value="C">ג׳ – כתיבת כיתובים (Captions)</option>
          </select>
        </div>
        <div className="field-group">
          <label>נתיב קובץ מקור (CSV)</label>
          <input type="text" value={source} onChange={(e) => setSource(e.target.value)} placeholder="למשל: backend/data/my_data.csv" />
          <p className="field-hint">הקובץ חייב להכיל את העמודות: TEXT ,IMAGE_URL</p>
        </div>
        <hr className="divider" />
        <div className="btn-row">
          <button className="btn btn-secondary" onClick={onBack}>ביטול</button>
          <button className="btn btn-primary" onClick={() => onSubmit({ name, workflow_type: workflow, source_csv: source })}>
            יצירת פרויקט
          </button>
        </div>
      </div>
    </section>
  );
}

function TaskScreen({ project, task, isFinished, onSubmit, onExit, error }) {
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
          </div>
          <button className="btn btn-secondary" style={{ padding: '8px 14px', minWidth: 'auto' }} onClick={onExit}>
            יציאה
          </button>
        </div>

        {task.has_image && (
          <div className="task-image-container">
            <img src={task.image_path} alt="Task" />
          </div>
        )}

        {task.has_text && (
          <div className="task-text-box">{task.text_content}</div>
        )}

        {error && <div className="alert alert-error">{error}</div>}

        <div id="task-fields">
          {project.workflow_type === 'A' && <WorkflowA onSubmit={onSubmit} />}
          {project.workflow_type === 'B' && <WorkflowB onSubmit={onSubmit} />}
          {project.workflow_type === 'C' && <WorkflowC onSubmit={onSubmit} />}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Workflow Specific Components
// ---------------------------------------------------------------------------

function WorkflowA({ onSubmit }) {
  const [selected, setSelected] = useState('');
  const choices = [
    { value: 'Independent', label: 'עצמאי – התמונה מספקת את המידע הנדרש' },
    { value: 'Context-Dependent', label: 'תלוי הקשר – נדרש הטקסט להבנה' },
    { value: 'Noise', label: 'רעש – אין קשר לוגי בין התמונה לטקסט' },
  ];

  return (
    <div>
      <h2>ניתוח הקשר בין תמונה לטקסט</h2>
      <div className="choice-group">
        {choices.map((c) => (
          <button
            key={c.value}
            className={`choice-btn ${selected === c.value ? 'selected' : ''}`}
            onClick={() => setSelected(c.value)}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="btn-row">
        <button className="btn btn-primary" onClick={() => selected && onSubmit({ relationship: selected })}>
          אישור ושליחה
        </button>
      </div>
    </div>
  );
}

function WorkflowB({ onSubmit }) {
  const [step, setStep] = useState(1);
  const [data, setData] = useState({ entity_name: '', entity_type: '', topic: '', sentiment: '' });

  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <div>
            <h2>שלב 1 – זיהוי ישות מרכזית</h2>
            <div className="field-group">
              <label>שם הישות</label>
              <input
                type="text"
                value={data.entity_name}
                onChange={(e) => setData({ ...data, entity_name: e.target.value })}
                placeholder="למשל: בנק ישראל"
              />
            </div>
            <div className="field-group">
              <label>סוג הישות</label>
              <div className="choice-group">
                {['Person', 'Org', 'Place'].map((t) => (
                  <button
                    key={t}
                    className={`choice-btn ${data.entity_type === t ? 'selected' : ''}`}
                    onClick={() => setData({ ...data, entity_type: t })}
                  >
                    {t === 'Person' ? '👤 אדם' : t === 'Org' ? '🏢 ארגון' : '📍 מקום'}
                  </button>
                ))}
              </div>
            </div>
            <button className="btn btn-primary" onClick={() => data.entity_name && data.entity_type && setStep(2)}>הבא ←</button>
          </div>
        );
      case 2:
        return (
          <div>
            <h2>שלב 2 – קביעת נושא הטקסט</h2>
            <div className="field-group">
              <label>הנושא העיקרי</label>
              <input
                type="text"
                value={data.topic}
                onChange={(e) => setData({ ...data, topic: e.target.value })}
                placeholder="למשל: שינויים בריבית במשק"
              />
            </div>
            <div className="btn-row">
              <button className="btn btn-secondary" onClick={() => setStep(1)}>חזור</button>
              <button className="btn btn-primary" onClick={() => data.topic && setStep(3)}>הבא ←</button>
            </div>
          </div>
        );
      case 3:
        return (
          <div>
            <h2>שלב 3 – הערכת סנטימנט</h2>
            <div className="choice-group">
              {['Good', 'Bad', 'Trust', 'Fear', 'Anger'].map((s) => (
                <button
                  key={s}
                  className={`choice-btn ${data.sentiment === s ? 'selected' : ''}`}
                  onClick={() => setData({ ...data, sentiment: s })}
                >
                  {s === 'Good' ? '😊 חיובי' : s === 'Bad' ? '😠 שלילי' : s}
                </button>
              ))}
            </div>
            <div className="btn-row">
              <button className="btn btn-secondary" onClick={() => setStep(2)}>חזור</button>
              <button className="btn btn-primary" onClick={() => data.sentiment && onSubmit(data)}>סיום ושליחה</button>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div>
      <div className="steps-indicator">
        {[1, 2, 3].map((s) => (
          <React.Fragment key={s}>
            <div className={`step-dot ${step === s ? 'active' : step > s ? 'done' : ''}`}>
              {step > s ? '✓' : s}
            </div>
            {s < 3 && <div className="step-line"></div>}
          </React.Fragment>
        ))}
      </div>
      {renderStep()}
    </div>
  );
}

function WorkflowC({ onSubmit }) {
  const [caption, setCaption] = useState('');

  return (
    <div>
      <h2>כתיבת כיתוב תיאורי (Caption)</h2>
      <p className="subtitle">תאר את התמונה באופן אקדמי ומדויק עבור קהל יעד מגוון.</p>
      <div className="field-group">
        <label>הכיתוב המוצע</label>
        <textarea
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          placeholder="תאר את הפרטים המופיעים בתמונה..."
        />
      </div>
      <div className="btn-row">
        <button className="btn btn-primary" onClick={() => caption && onSubmit({ caption })}>
          שלח כיתוב
        </button>
      </div>
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
