import os
import json
from flask import Blueprint, request, jsonify, current_app
import google.generativeai as genai
from google.generativeai import types

networking_bp = Blueprint('networking_bp', __name__, url_prefix='/networking')

genai_llm_search = None
LLM_MODEL = "gemini-2.5-flash-preview-09-2025"


def init_networking_services(app):
    global genai_llm_search
    app.logger.info("Initializing Networking Services (Google GenAI + Search)...")
    try:
        
        GOOGLE_API_KEY = os.getenv('VITE_GOOGLE_API_KEY')
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not set in .env file")
        
        genai.configure(api_key=GOOGLE_API_KEY)
        
        
        search_tool = types.Tool.from_google_search(
            retrieval=types.GoogleSearchRetrieval()
        )
        
        genai_llm_search = genai.GenerativeModel(
            model=LLM_MODEL,
            tools=[search_tool]
        )
        
        app.logger.info("Networking Services (Gemini + Google Search) initialized.")
    except Exception as e:
        app.logger.error(f"Error initializing Networking Services: {e}")


@networking_bp.route('/find-investors', methods=['POST'])
def find_investors(idea):

    if not genai_llm_search:
         current_app.logger.error("Networking LLM client not initialized")
         return jsonify({"error": "Networking client not initialized"}), 500

    data = request.json
    if 'idea' not in data:
        return jsonify({"error": "Missing 'idea' in request body"}), 400
    
    user_idea = idea
    
    system_instruction = """
    You are a startup advisor and venture capital networking expert. Your task is to:
    1.  Use Google Search to find 5-7 relevant, real-world venture capital firms or angel investors that match the user's startup idea.
    2.  For each investor, find their name (if a specific partner is relevant) or the firm's name, and a valid source URL.
    3.  For each, write a concise, professional, and compelling cold outreach email. The email should be a template, using placeholders like [Your Name] and [Startup Name]. It must introduce the idea, align with the investor's focus, and ask for a brief meeting.
    4.  You MUST return this information as a valid JSON array of objects. Do not return any other text.
    """
    
    investor_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "investor_name": {"type": "STRING"},
                "firm_name": {"type": "STRING"},
                "source_url": {"type": "STRING"},
                "source_title": {"type": "STRING"},
                "draft_email": {"type": "STRING"}
            },
            "required": ["investor_name", "firm_name", "source_url", "source_title", "draft_email"]
        }
    }
    
    generation_config = types.GenerationConfig(
        response_mime_type="application/json",
        response_schema=investor_schema
    )
    
    user_query = f"""
    Here is the startup idea: "{user_idea}".
    Please find a list of potential investors and draft outreach emails for me based on this idea.
    """
    
    try:
        chat_session = genai_llm_search.start_chat(
            generation_config=generation_config,
            system_instruction=system_instruction
        )
        response = chat_session.send_message(user_query)
        
        response_json = json.loads(response.text)
        
        citations = []
        if response.grounding_metadata:
            citations = [
                {
                    "uri": attr.web.uri,
                    "title": attr.web.title
                }
                for attr in response.grounding_metadata.grounding_attributions
            ]
        
        return jsonify({
            "investors": response_json,
            "sources": citations
        }), 200

    except Exception as e:
        current_app.logger.exception(f"Error in /networking/find-investors: {e}")
        return jsonify({"error": f"Failed to generate networking strategy: {str(e)}"}), 500