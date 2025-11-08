# pip install -r requirements.txt

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from run_deck import run_deck
from user_networking import init_networking_services, find_investors
#from ad_gen import ad_gen_bp, init_ad_gen_services
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
    data = request.get_json(silent=True) or {}
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
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Slide generation failed", exc_info=exc)
        return jsonify({'error': 'Slide generation failed'}), 500

    return jsonify({'presentationUrl': presentation_url})

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)