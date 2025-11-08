# pip install -r requirements.txt

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from slide_create import main as create_slides
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)

# Allow CORS from the Vite dev server (adjust origin as needed for production)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})

# Testing route
@app.route('/')
def hello_world():
    return 'kpop demon hunters RAHHHHHHHHH!'

@app.route('/create_slides', methods=['POST'])
def create_slides_route():
    data = request.json
    text = data.get('text')

    if not text:
        return jsonify({'error': 'Text is required'}), 400

    slides = create_slides(text)
    return jsonify({'slides': slides})

if __name__ == '__main__':
    app.run(debug=True, port=5000)