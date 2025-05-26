from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import json
import sqlite3

app = Flask(__name__)
CORS(app)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL_NAME = "qwen3:latest"  # Ensure this model is downloaded in Ollama
DATABASE_FILE = 'database.db'

def init_db():
    """Initializes the database and creates the table if it doesn't exist."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_prompt TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    print("Database initialized.")

@app.route('/')
def index():
    return send_from_directory('.', 'challenge_chatbot_html.html')

def format_prompt_with_context(prompt, context):
    """Formats the prompt with conversation history and Wazoku best practices for the AI model."""
    # Extract asked questions from system messages
    asked_questions = [item['content'].split(': ')[1] for item in context
                       if item['role'] == 'system' and 'question_asked' in item['content']]
    
    # Define the sequence of stages
    stages = ["description", "type", "goals", "prize", "timeline", "evaluation", "monitoring"]
    
    # Find the next stage that hasn’t been asked
    current_stage = None
    for stage in stages:
        if stage not in asked_questions:
            current_stage = stage
            break
    
    if current_stage:
        next_question = get_question_for_stage(current_stage)
    else:
        next_question = "All stages are complete. Would you like to review your challenge configuration?"
        current_stage = "complete" # Mark as complete when all questions are asked
    
    # Wazoku best practices instruction
    best_practices_instruction = (
        "You are a crowdsourcing challenge platform assistant. "
        "Guide the user through defining their challenge step-by-step, one stage/question at a time."
    )
    
    # Convert conversation history to string, excluding system messages
    history_str = "\n".join([f"{item['role']}: {item['content']}" 
                             for item in context if item['role'] != 'system'])
    
    final_prompt = (
        f"{best_practices_instruction}\n\n{history_str}\n"
        f"user: {prompt}\nassistant: {next_question}"
    )
    return final_prompt, current_stage

def get_question_for_stage(stage):
    """Helper function to get the question for a specific stage."""
    questions = {
        "description": "Please describe your challenge.",
        "type": "What type of challenge is this (e.g., Ideation, Design, Development, Data Science)?",
        "goals": "How does this challenge align with your organization's innovation goals?",
        "prize": (
            "How would you like to set up the prize structure (e.g., single winner, tiered, milestones)? "
            "Consider estimating prize amounts based on time, costs, effort, and expertise required. "
            "You can also index prizes from similar challenges on platforms like Kaggle or InnoCentive."
        ),
        "timeline": (
            "What are the start and end dates for the challenge? "
            "Would you like to define intermediate milestones (e.g., registration, submission, review)?"
        ),
        "evaluation": (
            "What evaluation model will you use (e.g., rolling or post-submission)? "
            "Please define reviewer roles, criteria, and whether you’d like peer review, automated AI review, or custom rubrics."
        ),
        "monitoring": (
            "How would you like to handle announcements and updates during the challenge? "
            "Regular updates can keep participants engaged and informed."
        )
    }
    return questions.get(stage, "All stages are complete. Would you like to review your challenge configuration?")

@app.route('/generate', methods=['POST'])
def generate_text():
    """Handles the main chat interaction and generates AI responses."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No input data provided"}), 400

        prompt = data.get('prompt')
        context_data = data.get('context', [])

        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        final_prompt_for_ollama, stage = format_prompt_with_context(prompt, context_data)

        print(f"Sending to Ollama - Model: {OLLAMA_MODEL_NAME}, Prompt: {final_prompt_for_ollama[:300]}...")

        ollama_payload = {
            "model": OLLAMA_MODEL_NAME,
            "prompt": final_prompt_for_ollama,
            "stream": False
        }

        response = requests.post(OLLAMA_API_URL, json=ollama_payload)
        response.raise_for_status()

        ollama_response_data = response.json()
        generated_text = ollama_response_data.get("response", "").strip()

        try:
            with sqlite3.connect(DATABASE_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO conversations (user_prompt, ai_response) VALUES (?, ?)",
                               (prompt, generated_text))
                conn.commit()
            print("Successfully saved conversation turn to database.")
        except Exception as db_error:
            print(f"Database Error: {db_error}")

        print(f"Ollama response received: {generated_text[:200]}...")
        
        return jsonify({
            "response": generated_text,
            "stage": stage,  # Include the stage in the response
            "thought_process": final_prompt_for_ollama
        })

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Ollama: {e}")
        return jsonify({"error": f"Could not connect to Ollama. Is it running? Details: {str(e)}"}), 500
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate_narrative', methods=['POST'])
def generate_narrative():
    """Generates a creative narrative for the challenge based on the conversation context."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No input data provided"}), 400

        context_data = data.get('context', [])

        # Extract challenge details from the conversation context
        challenge_details = {}
        # Iterate through the context to reconstruct the challenge details
        # Assuming the pattern is user_prompt -> AI_response (which contains the question asked)
        # and then user_prompt -> AI_response (which contains the answer)
        # This part needs to be robust based on how your context is structured.
        # For simplicity, let's just grab the last AI response for each stage.
        
        # A more robust way would be to parse the 'system' messages for 'question_asked'
        # and then find the subsequent user message as the answer to that question.
        
        # Let's refine this to extract the actual answers from the conversation flow.
        # We'll map the stage to the user's response to that stage's question.
        
        # This will store the key details for the narrative
        extracted_details = {
            "description": "", "type": "", "goals": "", "prize": "",
            "timeline": "", "evaluation": "", "monitoring": ""
        }
        
        # Go through the conversation history to extract answers to each stage
        current_question_stage = None
        for item in context_data:
            if item['role'] == 'system' and 'question_asked' in item['content']:
                current_question_stage = item['content'].split(': ')[1]
            elif item['role'] == 'user' and current_question_stage:
                # This user message is likely the answer to the last question asked
                if current_question_stage in extracted_details:
                    extracted_details[current_question_stage] = item['content']
                current_question_stage = None # Reset for the next question

        # Construct a detailed prompt for Ollama to generate the narrative
        narrative_prompt = (
            "You are a master storyteller and a marketing expert for a crowdsourcing platform. "
            "Your task is to craft a compelling, inspiring, and concise narrative for a new innovation challenge. "
            "Use the following details to create a story that excites potential participants and clearly communicates the challenge's purpose and impact. "
            "Focus on the 'why' and the potential for change, not just the 'what'. "
            "Do not include any conversational elements or questions in your response, just the narrative.\n\n"
            "Here are the challenge details:\n"
            f"Description: {extracted_details.get('description', 'Not provided')}\n"
            f"Type: {extracted_details.get('type', 'Not provided')}\n"
            f"Goals: {extracted_details.get('goals', 'Not provided')}\n"
            f"Prize Structure: {extracted_details.get('prize', 'Not provided')}\n"
            f"Timeline: {extracted_details.get('timeline', 'Not provided')}\n"
            f"Evaluation: {extracted_details.get('evaluation', 'Not provided')}\n"
            f"Monitoring: {extracted_details.get('monitoring', 'Not provided')}\n\n"
            "Please generate the challenge narrative:"
        )

        print(f"Sending to Ollama for narrative generation - Prompt: {narrative_prompt[:300]}...")

        ollama_payload = {
            "model": OLLAMA_MODEL_NAME,
            "prompt": narrative_prompt,
            "stream": False
        }

        response = requests.post(OLLAMA_API_URL, json=ollama_payload)
        response.raise_for_status()

        ollama_response_data = response.json()
        generated_narrative = ollama_response_data.get("response", "").strip()

        print(f"Ollama narrative received: {generated_narrative[:200]}...")
        
        return jsonify({
            "narrative": generated_narrative
        })

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Ollama: {e}")
        return jsonify({"error": f"Could not connect to Ollama for narrative. Is it running? Details: {str(e)}"}), 500
    except Exception as e:
        print(f"An error occurred during narrative generation: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    print(f"Starting Flask backend server for Qwen3 on http://localhost:5000")
    print(f"Ensure Ollama is running and model '{OLLAMA_MODEL_NAME}' is available.")
    app.run(debug=True, port=5000)
