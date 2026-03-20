from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

# Import the Pydantic schema we defined to validate incoming data
from schemas import TimetableRequest

# Import our custom modules
from llm_parser import apply_special_constraints
from scheduler import generate_schedule

# Initialize the FastAPI application
app = FastAPI(title="AI Timetable Generator")

# Mount the 'static' directory to serve index.html and style.css
# This ensures the browser can load your frontend UI
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serves the main Wizard UI when you visit the root URL."""
    # Check if the file exists to prevent server crashes
    if not os.path.exists("static/index.html"):
        return "<h1>Error: static/index.html not found!</h1>"
        
    with open("static/index.html", "r", encoding="utf-8") as file:
        return file.read()

from dotenv import load_dotenv
load_dotenv() # THIS IS NEW: Forces Python to read your .env file!

@app.post("/api/generate")
async def create_timetable(request: TimetableRequest):
    try:
        print("1. Received structured data from frontend.")
        base_data = request.dict()
        constraint_text = request.special_constraints
        
        # --- NEW SAFETY CATCH ---
        if not constraint_text or constraint_text.strip() == "":
            print("2. No AI constraints typed. Skipping internet LLM call.")
            updated_data = base_data # Skip the LLM completely
        else:
            print("2. Checking for LLM modifications over the internet...")
            updated_data = apply_special_constraints(base_data, constraint_text)
        # ------------------------
        
        print("3. Running the OR-Tools Mathematical Solver...")
        result = generate_schedule(updated_data)
        
        if result["status"] == "error":
            print(f"4. Solver Error: {result['message']}")
            raise HTTPException(status_code=400, detail=result["message"])
            
        print("4. Success! Returning timetable data.")
        return result

    except Exception as e:
        print(f"CRITICAL SYSTEM ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    # except Exception as e:
    #     # Catch any unexpected server errors and send a clean message back to the UI
    #     print(f"Server Error: {str(e)}")
    #     raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")