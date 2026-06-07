# Spotibine

Spotibine is a Spotify automation tool that lets you define track sequences and then automatically continue playback when the current song matches a saved sequence. The project combines a Flask backend with a React + Vite frontend.

## What it does

- Connects to Spotify with OAuth.
- Lets you create a sequence from a first track.
- Lets you extend that sequence with one or more continuation tracks.
- Shows saved sequences in the UI and lets you select or delete them.
- Monitors the active Spotify player and queues the configured continuation tracks when a matching song starts playing.
- Persists sequence data locally with pickle files so saved rules survive restarts.

## Tech Stack

- Backend: Python, Flask, Requests, python-dotenv
- Frontend: React, React Router, Vite
- Spotify integration: Spotify Web API and OAuth authorization flow
- Persistence: local pickle files stored at the repository root

## Project Structure

```text
Spotibine/
├── main.py
├── saved_link.p
├── saved_presentation.p
├── saved_sequences.p
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── styles.css
│       ├── api/
│       │   └── client.js
│       └── components/
│           ├── SequenceList.jsx
│           └── TrackForm.jsx
├── static/
│   └── styles/
└── Templates/
```

### Important files

- [main.py](main.py): Flask app, Spotify OAuth, API endpoints, automation worker, and persistence logic.
- [frontend/src/App.jsx](frontend/src/App.jsx): Main dashboard UI and routing.
- [frontend/src/api/client.js](frontend/src/api/client.js): Frontend API wrapper for backend calls.
- [frontend/src/components/TrackForm.jsx](frontend/src/components/TrackForm.jsx): Reusable form for track input.
- [frontend/src/components/SequenceList.jsx](frontend/src/components/SequenceList.jsx): Saved-sequence list and selection/delete controls.

## Requirements

- Python 3.10+ is recommended.
- Node.js 18+ is recommended.
- A Spotify Developer app with a valid client ID, client secret, and redirect URI.

## Environment Variables

Copy the `.env_sample` file in the repository root and provide the environment variable values:

```bash
CLIENT_ID = YOUR_SPOTIFY_CLIENT_ID_HERE
CLIENT_SECRET = YOUR_SPOTIFY_CLIENT_SECRET_HERE
FLASK_SECRET = YOUR_FLASK_SECRET_HERE
REDIRECT_URI = "http://127.0.0.1:5001/callback"
```

The `REDIRECT_URI` value must match the callback URL registered in your Spotify app settings.

## Running the Project

### 1. Start the backend

Install the Python dependencies first if you do not already have them:

```bash
pip install flask requests python-dotenv
```

Then run the Flask app:

```bash
python main.py
```

The backend starts on `http://127.0.0.1:5001`.

### 2. Start the frontend in development

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on `http://127.0.0.1:5173` and proxies `/api`, `/login`, and `/callback` to the Flask backend.

### 3. Open the app

- Development UI: `http://127.0.0.1:5173/app`
- Backend-served app: `http://127.0.0.1:5001/app`

## Production Build

The Flask app serves the React build from `frontend/dist` when it exists.

```bash
cd frontend
npm run build
cd ..
python main.py
```

After the build completes, open `http://127.0.0.1:5001/app`.

## How It Works

1. The user clicks Login with Spotify and completes the OAuth flow.
2. The backend stores the access token and refresh token in memory.
3. Creating a sequence searches Spotify for the requested song and saves its track URI as the first track in the sequence.
4. Extending a sequence searches for another song and appends that track URI as a continuation.
5. When automation is running, the backend polls the currently playing track and, on a match, queues the configured continuation tracks.

## Backend API Overview

- `GET /api/health`: health check
- `GET /api/auth/login-url`: returns the Spotify authorization URL
- `GET /api/auth/status`: returns authentication and selected-sequence state
- `GET /api/sequences`: returns saved sequences
- `POST /api/sequences`: creates a new sequence
- `POST /api/sequences/<sequence_uri>/tracks`: extends a sequence
- `POST /api/sequences/<sequence_uri>/select`: selects a sequence in the UI
- `DELETE /api/sequences/<sequence_uri>`: deletes a sequence
- `GET /api/automation/status`: returns automation state
- `POST /api/automation/start`: starts the background automation worker
- `POST /api/automation/stop`: stops the worker

## Data Storage

Spotibine stores sequence state locally in three pickle files at the repository root:

- `saved_sequences.p`: track URI sequences
- `saved_presentation.p`: display labels shown in the UI
- `saved_link.p`: mapping between labels and sequence URIs

Deleting these files resets the saved sequence data.

## Notes

- The automation worker runs in a background thread inside the Flask process.
- The backend expects an active Spotify device for queueing to work.
- The frontend uses relative API calls, so the Vite proxy is required during development.
