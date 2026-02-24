from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
import os

# ייבוא המחלקות המודולריות החדשות שלכם
import CSVreader
import sources
import data
import user
import server_functions

app = FastAPI(title="Labeling System - Modular API")

# הגדרת CORS - חשוב מאוד לתקשורת עם הפרונטנד
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ניהול מצב השרת (State) ---
# אנחנו ניצור אובייקט של מקור נתונים לכל פרויקט
projects_sources = {}
projects_config = CSVreader.load_projects_config()

# אתחול המקורות (לפי ה-Config של חבר 1)
for p_id, config in projects_config.items():
    if os.path.exists(config["source_file"]):
        projects_sources[p_id] = sources.Local_CSV_File(config["source_file"])

# --- Routes ---

@app.get("/")
async def root():
    return {"status": "API Master is Online", "mode": "Modular"}

@app.get("/projects")
async def get_projects():
    """מחזיר את רשימת הפרויקטים (מחבר 1)"""
    return projects_config

@app.get("/next-mission/{project_id}")
async def get_next_mission(project_id: str, user_name: str = "guest"):
    """
    מביא את המשימה הבאה:
    1. בודק אם לפרויקט יש נתונים.
    2. מושך את הנתון הבא מהמקור (בעזרת sources.py).
    3. מעבד אותו לאובייקט Data (בעזרת data.py).
    """
    if project_id not in projects_sources:
        raise HTTPException(status_code=404, detail="Project or data source not found")
    
    source = projects_sources[project_id]
    
    if source.is_empty():
        raise HTTPException(status_code=404, detail="No more data available for this project")
    
    # שליפת נתון גולמי (מערך) והפיכתו לאובייקט Data חכם
    # בעזרת הפונקציה המדויקת שלקוחה מ-data.py, שבה הוגדר שטקסט עמודה 0 ותמונה עמודה 1
    try:
        mission_obj = data.get_data_from_source(source, 0, 1)
        
        return {
            "project_id": project_id,
            "data": {
                "text_content": mission_obj.get_text(),
                "image_url": mission_obj.get_image_url()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.post("/submit-label")
async def submit_label(
    project_id: str = Body(...),
    label_data: Dict[str, Any] = Body(...),
    user_name: str = Body("guest")
):
    """
    שומר את התיוג:
    1. משתמש ב-CSVreader לשמירה פיזית.
    2. משתמש ב-server_functions לניהול המשתמש.
    """
    if project_id not in projects_config:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects_config[project_id]
    
    # הכנת השורה לשמירה (מצרפים מטא-דאטה)
    submission = {
        **label_data,
        "labeler_id": user_name
    }
    
    # שמירה פיזית לקובץ (חבר 1)
    success = CSVreader.append_to_master(
        project["master_file"],
        submission,
        project["all_fields"]
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save results")
    
    return {"status": "success", "user": user_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
