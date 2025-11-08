# Before running, run "pip install -r requirements.txt" in venv

from flask import Flask, jsonify, request
from dotenv import load_dotenv
from python_files.slide_create import main as create_slides

load_dotenv()

app = Flask(__name__)

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