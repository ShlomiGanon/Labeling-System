import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import LabelingWorkspace from './pages/LabelingWorkspace';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      {/* 
        כאן מוגדר "לוח המרכזייה" של האפליקציה. 
        זה אומר שהדף הזה לא עושה בעצמו כלום, אלא רק מנתב לדפים האחרים (מודולריות מלאה!)
      */}
      <Routes>
        <Route path="/" element={<LandingPage />} />
        
        {/* הנתיב הזה כולל את המזהה של הפרויקט כמשתנה (projectId) */}
        <Route path="/labeling/:projectId" element={<LabelingWorkspace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
