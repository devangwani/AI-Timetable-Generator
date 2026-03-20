from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import json

from schemas import TimetableRequest
from llm_parser import apply_special_constraints
from scheduler import generate_schedule
from dotenv import load_dotenv

load_dotenv() 

app = FastAPI(title="AI Timetable Generator")
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_FILE = "database.json"

# --- DATABASE HELPERS ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return []

def save_to_db(new_records):
    db = load_db()
    # Find which divisions we are updating (e.g., SY_A)
    divs_being_updated = set([r['division'] for r in new_records])
    
    # Keep everything in the DB *except* the divisions we are overwriting right now
    # This prevents the DB from duplicating if you regenerate SY multiple times
    db = [r for r in db if r['division'] not in divs_being_updated]
    
    db.extend(new_records)
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)
# ------------------------

@app.get("/", response_class=HTMLResponse)
async def read_root():
    if not os.path.exists("static/index.html"):
        return "<h1>Error: static/index.html not found!</h1>"
    with open("static/index.html", "r", encoding="utf-8") as file:
        return file.read()

@app.post("/api/generate")
async def create_timetable(request: TimetableRequest):
    try:
        base_data = request.dict()
        constraint_text = request.special_constraints
        
        if not constraint_text or constraint_text.strip() == "":
            updated_data = base_data 
        else:
            updated_data = apply_special_constraints(base_data, constraint_text)
            
        # --- GLOBAL ANTI-CLASH LOGIC ---
        db = load_db()
        current_divs = [d["name"] for d in updated_data.get("divisions", [])]
        locked_slots = {"faculty": {}, "rooms": {}}
        
        for row in db:
            # Only lock slots from OTHER divisions (e.g., lock SY while generating TY)
            if row["division"] in current_divs:
                continue 
                
            fac = row["faculty"]
            room = row["room"]
            day = row["day"]
            h = row["hour"]

            if fac not in locked_slots["faculty"]: locked_slots["faculty"][fac] = []
            locked_slots["faculty"][fac].append((day, h))

            if room not in locked_slots["rooms"]: locked_slots["rooms"][room] = []
            locked_slots["rooms"][room].append((day, h))
        # -------------------------------

        # Pass the locked slots to the math solver
        result = generate_schedule(updated_data, locked_slots)
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
            
        # Save the successful raw data to our permanent database
        save_to_db(result["raw_data"])
        
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- NEW: FACULTY SEARCH ENDPOINT ---
@app.get("/api/faculty/{faculty_name}")
async def get_faculty_schedule(faculty_name: str):
    db = load_db()
    # Find all classes assigned to this teacher across all years
    my_classes = [r for r in db if r['faculty'].lower() == faculty_name.lower()]
    
    if not my_classes:
        raise HTTPException(status_code=404, detail=f"No schedule found for {faculty_name.upper()}")

    # Build an empty schedule grid
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule = {day: {str(h): "-" for h in range(8, 18)} for day in days}

    # Populate the grid with the teacher's classes
    for c in my_classes:
        day = c["day"]
        h = str(c["hour"])
        
        # Format it exactly like the student view, but prioritize the Class Name
        content = f"<strong>{c['subject']} ({c['division']})</strong><br><small>{c['room']}</small>"
        
        if schedule[day][h] == "-":
            schedule[day][h] = content
        else:
            # If they have multiple batches in parallel, stack them
            schedule[day][h] += f"<hr style='margin:8px 0; border:none; border-top:1px dashed rgba(255,255,255,0.15);'>{content}"

    # Return it wrapped in the teacher's name so the frontend can reuse the render function!
    return {"status": "success", "data": {faculty_name.upper(): schedule}}