import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Load the environment variables from the .env file
load_dotenv()

# Securely fetch the API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("CRITICAL ERROR: GEMINI_API_KEY not found in .env file.")

# Configure the Gemini API
genai.configure(api_key=api_key)

# Initialize the model. 
# We use gemini-2.5-flash because it is extremely fast and cost-effective for data formatting.
# The generation_config strictly forces the LLM to output ONLY valid JSON, preventing markdown formatting errors.
model = genai.GenerativeModel(
    'gemini-2.5-flash',
    generation_config={"response_mime_type": "application/json"}
)

def apply_special_constraints(base_data: dict, constraint_text: str) -> dict:
    """
    Takes the structured JSON from the UI and the user's plain-text rules,
    asks Gemini to modify the JSON based on the rules, and returns the updated JSON.
    """
    
    # If the user didn't type any special constraints, just return the original data to save time and API calls
    if not constraint_text or constraint_text.strip() == "":
        print("No special constraints provided. Skipping LLM processing.")
        return base_data

    # The Prompt: Instructing the LLM exactly how to handle the data
    prompt = f"""
    You are an expert AI scheduling assistant for an engineering college. 
    I am providing you with a baseline JSON object representing a university timetable setup (Divisions, Subjects, Batches, etc.).
    
    Baseline JSON:
    {json.dumps(base_data)}
    
    The user has provided the following special constraints in plain text:
    "{constraint_text}"
    
    Your task is to act as a Natural Language Processor. Analyze the text and modify the JSON to reflect these constraints. 
    For example: 
    - If the user says "WP only has 2 theory lectures", find the subject named "WP" and change "theory_lectures_per_week" to 2.
    - If the user says "DAA does not have labs", find "DAA" and change "has_lab" to false, and clear the batches array.
    
    Return ONLY the updated JSON object. Keep the exact same schema. Do not change division names or unrelated data.
    """

    try:
        # Call the Gemini API
        response = model.generate_content(prompt)
        
        # Because we enforced the JSON MIME type, response.text is guaranteed to be a JSON string
        updated_json = json.loads(response.text)
        print("Successfully applied special constraints via LLM.")
        return updated_json
        
    except json.JSONDecodeError as e:
        # Fallback 1: If the LLM somehow messes up the JSON structure
        print(f"Error decoding JSON from LLM: {e}")
        print("Falling back to baseline data.")
        return base_data
        
    except Exception as e:
        # Fallback 2: Catch network errors, API quota limits, etc.
        print(f"Unexpected error communicating with Gemini API: {e}")
        print("Falling back to baseline data.")
        return base_data