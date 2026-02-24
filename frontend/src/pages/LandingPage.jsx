import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';

export default function LandingPage() {
  const [projects, setProjects] = useState({});
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // טוענים את הפרויקטים מהשרת כשהדף עולה
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const data = await api.getProjects();
      setProjects(data);
    } catch (err) {
      console.error("Error fetching projects:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1>Labeling System</h1>
      <p>Select a project to start labeling</p>

      {loading ? (
        <p>Loading projects...</p>
      ) : (
        <div className="grid">
          {Object.entries(projects).map(([id, config]) => (
            <div key={id} className="card">
              <h3>{config.name}</h3>
              <p>{config.description || 'Start categorizing data faster.'}</p>
              
              {/* כפתור למעבר לדף התיוג בעזרת React Router */}
              <button onClick={() => navigate(`/labeling/${id}`)}>
                Select Project
              </button>
            </div>
          ))}
          
          {/* הכנה לדף היצירה שעתיד לבוא */}
          <div className="card" style={{ borderStyle: 'dashed' }}>
             <h3>+ New Project</h3>
             <p>Create a new labeling workflow.</p>
             <button onClick={() => navigate('/create-project')} disabled>
               Coming Soon
             </button>
          </div>
        </div>
      )}
    </div>
  );
}
