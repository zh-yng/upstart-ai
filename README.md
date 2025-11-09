<img width="713" height="247" alt="image" src="https://github.com/user-attachments/assets/e7fe5d77-3715-4dfa-80ec-420b867e922c" />



# Upstart AI

Upstart AI converts short prompts into lightweight slide decks. The frontend is implemented using React and Vite. The slide generation and related utilities are implemented in a Flask-based Python backend. The application is intended for rapid demonstration and evaluation: submit a prompt and receive a shareable presentation URL.

Key capabilities
- End-to-end prompt-to-slide generation.
- Modular backend utilities for slide composition, video generation, and startup/business consultation.
- Developer-friendly: simple local setup and clear separation between frontend and backend.

Technology
- Frontend: React + Vite
- Dev server/shim: Node (Express + vite-express)
- Backend: Flask (Python), Gemini API, Vertex AI

Repository structure (high level)
- `src/` — React application source
- `server.js` — Node server that runs the Vite dev server and a small set of development endpoints
- `backend/api/` — Flask application and generation utilities (e.g., `slide_create.py`, `run_deck.py`)

Prerequisites
- Node.js 18 or later
- Python 3.9 or later and `pip`
- (Optional) Google service account credentials or other API keys required for optional features. Place credentials in `backend/api/credentials.json` or `backend/api/token.json` as appropriate.

Local development
Start the backend (Flask)

```bash
cd backend/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Start the frontend and development server

```bash
cd <repo-root>
npm install
# Starts the Vite dev server
npm run dev
```

Production
- Build static assets: `npm run build`.
- Serve the built assets using a static server or CDN.
- Run the Flask application behind a WSGI server for production, for example:

```bash
gunicorn app:app -b 0.0.0.0:5000
```

Environment and credentials
- The backend uses environment variables (via `python-dotenv`). For integrations that require credentials, add the files to `backend/api/` or set the appropriate environment variables.

Troubleshooting
- Ports: development uses 5173 (frontend) and 5000 (backend). If those ports are in use, stop conflicting services or change the port configuration.
- Python errors: ensure the virtual environment is active and dependencies from `backend/api/requirements.txt` are installed.
- Missing credentials: features that rely on external APIs may fail or return restricted results without valid credentials.


License

This project is licensed under the MIT License.


