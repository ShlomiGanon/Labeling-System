import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';

export default function LabelingWorkspace() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  
  const [currentMission, setCurrentMission] = useState(null);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({});

  useEffect(() => {
    fetchNextMission();
  }, [projectId]);

  const fetchNextMission = async () => {
    setLoading(true);
    try {
      const mission = await api.getNextMission(projectId);
      setCurrentMission(mission);
      setFormData({}); // ניקוי הטופס למשימה החדשה
    } catch (err) {
      console.error("No more missions or error:", err);
      setCurrentMission(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      // שליחת הנתונים דרך ה-API שיצרנו
      await api.submitLabel({
        project_id: projectId,
        label_data: formData,
        user_name: 'user_1' // כאן בהמשך אפשר לשים שם משתמש אמיתי
      });
      // משיכת המשימה הבאה מיד אחרי ההצלחה
      fetchNextMission();
    } catch (err) {
      console.error(err);
      alert("Failed to submit label");
    }
  };

  return (
    <div className="container mission-card">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <button onClick={() => navigate('/')} style={{ background: 'rgba(255,255,255,0.05)' }}>← Projects</button>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ margin: 0 }}>Project: {projectId}</h2>
        </div>
        <div style={{ width: '80px', color: '#94a3b8', fontSize: '0.9rem' }}>
          {/* אפשר להוסיף כאן מספור שורות אם ה-API יחזיר */}
        </div>
      </header>

      {loading ? (
        <div className="card">
          <div className="loader">Loading Next Mission...</div>
        </div>
      ) : currentMission ? (
        <div className="grid">
          
          {/* צד שמאל: תצוגת התמונה והטקסט */}
          <div className="card">
            {currentMission.data.image_url && (
              <div className="media-container" style={{ marginBottom: '1rem', background: '#000', borderRadius: '12px', overflow: 'hidden' }}>
                <img src={currentMission.data.image_url} alt="To Label" style={{ maxHeight: '400px', objectFit: 'contain' }} />
              </div>
            )}
            {/* הטקסט */}
            {currentMission.data.text_content && (
               <div style={{ textAlign: 'left', fontSize: '1.25rem', whiteSpace: 'pre-wrap', color: '#e2e8f0', background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px' }}>
                  {currentMission.data.text_content}
               </div>
            )}
          </div>

          {/* צד ימין: טופס התיוג - לפי ה-Internship Document! */}
          <div className="card">
            <h4 style={{ textAlign: 'left', marginTop: 0, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '1px', fontSize: '0.8rem' }}>Task Details</h4>
            <form onSubmit={handleSubmit}>
              
              {/* === WORKFLOW A: Image-Text Relationship === */}
              {projectId === 'Workflow_A' && (
                <div className="input-group">
                  <label>How does the image relate to the text?</label>
                  <div className="button-group">
                    {[
                      { id: 'Independent', label: 'Independent', sub: 'The image alone explains the topic.' },
                      { id: 'Context-Dependent', label: 'Context-Dependent', sub: 'Image adds value but requires text.' },
                      { id: 'Noise', label: 'Noise', sub: 'The image is irrelevant to the text.' }
                    ].map(opt => (
                      <div 
                        key={opt.id}
                        className={`selectable-button ${formData.relationship === opt.id ? 'selected' : ''}`}
                        onClick={() => setFormData({...formData, relationship: opt.id})}
                      >
                         <div className="check-circle">{formData.relationship === opt.id ? '✓' : ''}</div>
                         <div>
                            <div style={{ fontSize: '1rem', fontWeight: '500' }}>{opt.label}</div>
                            <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>{opt.sub}</div>
                         </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* === WORKFLOW B: Semantic & Emotion === */}
              {projectId === 'Workflow_B' && (
                <>
                  <div className="input-group">
                    <label>Entity Identification (Person, Org, Place)</label>
                    <input 
                      placeholder="e.g. Elon Musk, NASA, SpaceX..."
                      type="text" required
                      value={formData.entity || ''} 
                      onChange={e => setFormData({...formData, entity: e.target.value})}
                    />
                  </div>
                  <div className="input-group">
                    <label>Topic Assignment</label>
                    <input 
                      placeholder="What is the main topic?"
                      type="text" required
                      value={formData.topic || ''} 
                      onChange={e => setFormData({...formData, topic: e.target.value})}
                    />
                  </div>
                  <div className="input-group">
                    <label>Sentiment/Emotion (toward the entity)</label>
                    <select 
                      required
                      value={formData.sentiment || ''} 
                      onChange={e => setFormData({...formData, sentiment: e.target.value})}
                    >
                      <option value="" disabled>Select emotion...</option>
                      <option value="Good">Good</option>
                      <option value="Bad">Bad</option>
                      <option value="Trust">Trust</option>
                      <option value="Fear">Fear</option>
                      <option value="Anger">Anger</option>
                    </select>
                  </div>
                </>
              )}

              {/* === WORKFLOW C: Caption === */}
              {projectId === 'Workflow_C' && (
                <div className="input-group">
                  <label>Golden Caption</label>
                  <textarea 
                    placeholder="Write a descriptive caption for this image..."
                    rows="6" required
                    value={formData.caption || ''} 
                    onChange={e => setFormData({...formData, caption: e.target.value})}
                  />
                </div>
              )}

              {/* Fallback for unrecognized project names (like Project_1 instead of Workflow_A) */}
              {!['Workflow_A', 'Workflow_B', 'Workflow_C'].includes(projectId) && (
                <div className="input-group" style={{ background: 'rgba(239,68,68,0.1)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(239,68,68,0.3)' }}>
                  <p style={{ margin: 0, color: '#fca5a5', fontSize: '0.9rem' }}>
                    <strong>Notice:</strong> Your project ID is "<b>{projectId}</b>". Please rename it in `CSVreader.py` to "<b>Workflow_A</b>", "<b>Workflow_B</b>", or "<b>Workflow_C</b>" to see the correct labeling forms.
                  </p>
                  <div style={{ marginTop: '1rem' }}>
                    <label>Fallback Answer Box</label>
                    <input 
                      placeholder="Type answer here..."
                      type="text" required
                      value={formData.fallback || ''} 
                      onChange={e => setFormData({...formData, fallback: e.target.value})}
                    />
                  </div>
                </div>
              )}


              <button 
                type="submit" 
                disabled={!Object.keys(formData).length}
                style={{ 
                  width: '100%', 
                  marginTop: '1.5rem', 
                  padding: '1rem',
                  background: '#38bdf8', 
                  color: '#0f172a', 
                  fontWeight: '700',
                  fontSize: '1.1rem',
                  opacity: !Object.keys(formData).length ? 0.5 : 1
                }}
              >
                Submit & Next →
              </button>
              
              <button 
                type="button" 
                onClick={fetchNextMission}
                style={{ width: '100%', marginTop: '0.75rem', background: 'transparent', border: '1px solid #334155', color: '#94a3b8' }}
              >
                Skip This One
              </button>
            </form>
          </div>
        </div>
      ) : (
        <div className="card">
          <h3>🎉 No More Data!</h3>
          <p>All records for this project have been read or labeled.</p>
          <button onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>Back to Projects Menu</button>
        </div>
      )}
    </div>
  );
}
