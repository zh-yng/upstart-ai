from flask import Flask
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Testing route
@app.route('/')
def hello_world():
    return 'kpop demon hunters RAHHHHHHHHH!'

if __name__ == '__main__':
    app.run(debug=True, port=5000)