# pip install -r requirements.txt

from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from run_deck import run_deck
from ad_gen import generate_video
from user_networking import init_networking_services, find_investors
import os
from google import genai
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)

# Allow CORS from the Vite dev server (adjust origin as needed for production)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})

# Initialize ad generation services and register blueprint
#init_ad_gen_services(app)
#app.register_blueprint(ad_gen_bp)

# Testing route
@app.route('/')
def hello_world():
    return 'kpop demon hunters RAHHHHHHHHH!'

@app.route('/create_slides', methods=['POST'])
def create_slides_route():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        app.logger.error(f"Failed to parse JSON: {e}")
        app.logger.error(f"Request data: {request.data}")
        app.logger.error(f"Content-Type: {request.content_type}")
        return jsonify({'error': 'Invalid JSON in request body'}), 400
    
    if not data:
        return jsonify({'error': 'Request body is empty'}), 400
    
    prompt_text = (data.get('text') or '').strip()
    author_name = data.get('author')
    include_images_value = data.get('includeImages', True)

    if not prompt_text:
        return jsonify({'error': 'Text is required'}), 400

    if isinstance(include_images_value, str):
        include_images_flag = include_images_value.strip().lower() not in {'0', 'false', 'off', 'no'}
    else:
        include_images_flag = bool(include_images_value)

    try:
        presentation_url = run_deck(
            prompt_text,
            author=author_name,
            include_images=include_images_flag,
        )
        app.logger.info(f"Presentation URL: {presentation_url}")
    except ValueError as exc:
        app.logger.error(f"ValueError in run_deck: {exc}")
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Slide generation failed", exc_info=exc)
        return jsonify({'error': 'Slide generation failed'}), 500

    if not presentation_url:
        app.logger.error("presentation_url is empty or None")
        return jsonify({'error': 'Failed to create presentation'}), 500

    return jsonify({'presentationUrl': presentation_url})

@app.route('/create_roadmap', methods=['POST'])
def create_roadmap_route():
    data = request.get_json(silent=True) or {}
    prompt_text = (data.get('text') or '').strip()
    download = data.get('download', False)

    if not prompt_text:
        return jsonify({'error': 'Text is required'}), 400

    try:
        # Get API key
        api_key = os.getenv("VITE_GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GOOGLE_API_KEY environment variable.")

        # Generate roadmap content
        client = genai.Client(api_key=api_key)
        
        prompt = f"""Create a comprehensive, actionable roadmap for the following startup idea: {prompt_text}

Structure the roadmap as a step-by-step guide with the following format:

# Startup Roadmap: [Startup Name]

## Phase 1: [Phase Name] (Timeline)
Brief description of this phase's objectives.

### Major Step 1: [Step Title]
- Sub-step 1: Detailed action item
- Sub-step 2: Detailed action item
- Sub-step 3: Detailed action item

### Major Step 2: [Step Title]
- Sub-step 1: Detailed action item
- Sub-step 2: Detailed action item
- Sub-step 3: Detailed action item

## Phase 2: [Phase Name] (Timeline)
Brief description of this phase's objectives.

[Continue pattern...]

Requirements:
- Create 4-6 major phases (e.g., Foundation, Product Development, Market Launch, Growth, Scale)
- Each phase should have 3-5 major steps
- Each major step should have 3-6 detailed sub-steps with specific, actionable tasks
- Include realistic timelines for each phase
- Be specific and practical - avoid generic advice
- Focus on concrete actions, not just concepts
- Do NOT use ** for bold formatting, use plain text only
- Number the phases and major steps clearly

Make it comprehensive but practical for a startup founder to follow."""

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
        )

        roadmap_text = response.text or "No roadmap content generated."

        # Generate PDF
        file_name = "roadmap.pdf"
        file_path = os.path.join(os.getcwd(), file_name)

        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        styles = getSampleStyleSheet()
        style_normal = styles['Normal']
        style_heading = styles['Heading1']

        story = []

        for line in roadmap_text.splitlines():
            if line.strip():
                if line.startswith('#'):
                    clean_line = line.lstrip('#').strip()
                    clean_line = clean_line.replace('**', '')
                    para = Paragraph(clean_line, style_heading)
                else:
                    clean_line = line.replace('**', '')
                    clean_line = clean_line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    para = Paragraph(clean_line, style_normal)
                story.append(para)
                story.append(Spacer(1, 0.1*inch))

        doc.build(story)

        # Return file based on download parameter
        if download:
            return send_file(file_path, as_attachment=True, download_name='startup_roadmap.pdf', mimetype='application/pdf')
        else:
            return send_file(file_path, as_attachment=False, mimetype='application/pdf')

    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Roadmap generation failed", exc_info=exc)
        return jsonify({'error': 'Roadmap generation failed'}), 500

@app.route('/create_video', methods=['POST'])
def create_video_route():
    data = request.get_json(silent=True) or {}
    prompt_text = (data.get('text') or '').strip()
    download = data.get('download', False)

    if not prompt_text:
        return jsonify({'error': 'Text is required'}), 400

    try:
        # Generate video
        file_name = "startup_ad_video.mp4"
        file_path = os.path.join(os.getcwd(), file_name)
        
        generate_video(prompt_text, file_path)

        # Return file based on download parameter
        if download:
            return send_file(file_path, as_attachment=True, download_name='startup_ad_video.mp4', mimetype='video/mp4')
        else:
            return send_file(file_path, as_attachment=False, mimetype='video/mp4')

    except RuntimeError as exc:
        error_msg = str(exc)
        if "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            return jsonify({'error': 'Video generation quota exceeded. Veo requires special access.'}), 429
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Video generation failed", exc_info=exc)
        return jsonify({'error': 'Video generation failed'}), 500

@app.route('/create_network', methods=['POST'])
def create_network_route():
    data = request.get_json(silent=True) or {}
    try:
        idea = (data.get('idea') or '').strip()
        if not idea:
            return jsonify({'error': 'Idea is required'}), 400
        output = find_investors(idea)
        return jsonify({'idea': output})
    except Exception as exc:
        app.logger.exception("Network generation failed", exc_info=exc)
        return jsonify({'error': 'Network generation failed'}), 500

@app.route('/chat', methods=['POST'])
def chat_route():
    """Handle chatbot interactions"""
    from agenticChatBot import handle_chat
    
    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    business_idea = (data.get('businessIdea') or '').strip()
    chat_history = data.get('chatHistory', [])
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        result = handle_chat(user_message, business_idea, chat_history)
        return jsonify(result)
    except Exception as exc:
        app.logger.exception("Chat processing failed", exc_info=exc)
        return jsonify({'error': 'Chat processing failed', 'response': 'Sorry, something went wrong. Please try again.'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)