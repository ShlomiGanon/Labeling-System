import csv
import os

# --- Issue #1.1: CSV Reader Module ---
def load_csv_file(file_path):
    """
    Loads only the first two columns into a 2D array.
    Raises an exception if any row has more than 2 columns.
    """
    data_array = []
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at: {file_path}")

    with open(file_path, mode='r', encoding='utf-8', newline='') as csvfile:
        reader = csv.reader(csvfile)
        
        for line_num, row in enumerate(reader, start=1):
            # Strict check: If row has more than 2 columns, raise exception
            if len(row) > 2:
                raise ValueError(f"Invalid format: Found {len(row)} columns at line {line_num}. Only 2 columns allowed.")
            
            # If a row is completely empty, we skip it; if it has 1 column, we raise an error
            if len(row) == 0:
                continue
            if len(row) < 2:
                raise ValueError(f"Invalid format: Line {line_num} contains only 1 column. Expected 2.")
            
            # Append the first two columns
            data_array.append([row[0], row[1]])
            
    return data_array

# --- Issue #1.2: Master Labels Writer ---
def append_to_master(master_file_path, label_data, fieldnames):
    """
    מוסיפה שורת תיוג חדשה לקובץ ה-Master.
    חבר צוות 3 (API) יקרא לפונקציה הזו כשהמשתמש ילחץ 'Submit'.
    """
    try:
        file_exists = os.path.isfile(master_file_path)
        with open(master_file_path, mode='a', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # אם הקובץ נוצר עכשיו, נכתוב את הכותרות
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(label_data)
        return True
    except Exception as e:
        print(f"Error appending to master: {e}")
        return False

# --- Issue #1.3: Project Config Loader ---
def load_projects_config():
    """
    טוענת את רשימת הפרויקטים וההגדרות שלהם.
    זה המקום להגדיר אילו שדות תיוג נדרשים לכל פרויקט.
    """
    # בעתיד אפשר להעביר את זה לקובץ JSON חיצוני, כרגע זה מוגדר כאן (Data Architect's responsibility)
    projects = {
        "Project_1": {
            "name": "Image & Text Validation",
            "source_file": "data/source_1.csv",
            "master_file": "data/master_labels_1.csv",
            "source_fields": ["URL", "Text", "Images", "original_index"],
            "label_fields": ["is_appropriate", "language", "labeler_comments"]
        },
        "Project_2": {
            "name": "Product Categorization",
            "source_file": "data/source_2.csv",
            "master_file": "data/master_labels_2.csv",
            "source_fields": ["URL", "Text", "Images", "original_index"],
            "label_fields": ["category", "brand", "is_duplicate"]
        }
    }
    
    # חישוב ה-all_fields לכל פרויקט (נדרש עבור ה-Writer)
    for p_id in projects:
        projects[p_id]["all_fields"] = projects[p_id]["source_fields"] + projects[p_id]["label_fields"]
        
    return projects

# --- פונקציית עזר (בונוס לארכיטקט) ---
def get_labeled_indices(master_file_path):
    """
    מחזירה סט של כל האינדקסים שכבר תויגו.
    חבר צוות 2 (Logic) יצטרך את זה כדי לדעת מה המשימה הבאה.
    """
    labeled_indices = set()
    if not os.path.exists(master_file_path):
        return labeled_indices
        
    try:
        with open(master_file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if 'original_index' in row:
                    labeled_indices.add(int(row['original_index']))
    except Exception as e:
        print(f"Error reading master indices: {e}")
    return labeled_indices