from dotenv import load_dotenv
import os
from requests import post, get
import urllib.parse
from flask import Flask, redirect, request, jsonify, send_from_directory
from datetime import datetime
import time
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional

import pickle

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_url = os.getenv("REDIRECT_URI")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET")
api_base_url = "https://api.spotify.com/v1/"
base_dir = os.path.dirname(os.path.abspath(__file__))
react_dist_dir = os.path.join(base_dir, "frontend", "dist")

state_lock = Lock()
stop_event = Event()
automation_thread: Optional[Thread] = None

app_state: Dict[str, Any] = {
    "access_token": "",
    "refresh_token": "",
    "expires_at": 0.0,
    "current_track": "",
    "active_device": "",
    "selected_sequence": None,
    "processing_ran": False,
}


def load_pickle_file(file_path: str, default_value: Any) -> Any:
    open(file_path, "ab").close()
    if os.path.getsize(file_path) == 0:
        return default_value
    try:
        with open(file_path, "rb") as file_obj:
            return pickle.load(file_obj)
    except (pickle.PickleError, EOFError):
        return default_value


def save_pickle_file(file_path: str, value: Any) -> None:
    with open(file_path, "wb") as file_obj:
        pickle.dump(value, file_obj)


def ensure_unique_presentation_name(base_name: str, existing: Dict[str, str]) -> str:
    if base_name not in existing:
        return base_name

    counter = 2
    candidate = f"{base_name} ({counter})"
    while candidate in existing:
        counter += 1
        candidate = f"{base_name} ({counter})"
    return candidate


def set_sequence_presentation(sequence_uri: str, new_value: str) -> str:
    global track_presentation, link_seq

    old_label = None
    for label, uri in link_seq.items():
        if uri == sequence_uri:
            old_label = label
            break

    if old_label is not None:
        link_seq.pop(old_label, None)
        if old_label in track_presentation:
            idx = track_presentation.index(old_label)
            track_presentation[idx] = new_value
        else:
            track_presentation.append(new_value)
    else:
        track_presentation.append(new_value)

    unique_label = ensure_unique_presentation_name(new_value, link_seq)
    if unique_label != new_value:
        if new_value in track_presentation:
            idx = track_presentation.index(new_value)
            track_presentation[idx] = unique_label
        else:
            track_presentation.append(unique_label)
        new_value = unique_label

    link_seq[new_value] = sequence_uri
    return new_value


def persist_all() -> None:
    save_pickle_file(os.path.join(base_dir, "saved_link.p"), link_seq)
    save_pickle_file(os.path.join(base_dir, "saved_presentation.p"), track_presentation)
    save_pickle_file(os.path.join(base_dir, "saved_sequences.p"), track_sequences)


def is_authenticated() -> bool:
    return bool(app_state.get("access_token"))


def refresh_access_token_if_needed() -> bool:
    if not app_state.get("access_token"):
        return False

    if datetime.now().timestamp() + 60 <= float(app_state.get("expires_at", 0)):
        return True

    refresh_token_value = app_state.get("refresh_token")
    if not refresh_token_value:
        return False

    req_body = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token_value,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    response = post("https://accounts.spotify.com/api/token", data=req_body)
    token_data = response.json()

    if "access_token" not in token_data:
        return False

    app_state["access_token"] = token_data["access_token"]
    app_state["expires_at"] = datetime.now().timestamp() + token_data.get("expires_in", 3600)
    return True


def auth_headers() -> Dict[str, str]:
    return {"Authorization": "Bearer " + app_state["access_token"]}


def auth_error_response():
    if not is_authenticated():
        return jsonify({"error": "Spotify account is not connected."}), 401
    if not refresh_access_token_if_needed():
        return jsonify({"error": "Spotify token has expired. Please reconnect."}), 401
    return None


def spotify_search_track(song_name: str, artist_name: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    query = f"{song_name} artist:{artist_name}".strip()
    response = get(
        api_base_url + "search",
        headers=headers,
        params={"q": query, "type": "track", "limit": 1},
    )
    items = response.json().get("tracks", {}).get("items", [])
    return items[0] if items else None


def get_sequence_summary() -> List[Dict[str, Any]]:
    """Return sequence data in UI-friendly order."""
    sequences: List[Dict[str, Any]] = []
    seen = set()

    for label in track_presentation:
        sequence_uri = link_seq.get(label)
        if not sequence_uri or sequence_uri not in track_sequences:
            continue
        sequences.append(
            {
                "id": sequence_uri,
                "presentation": label,
                "tracks": track_sequences.get(sequence_uri, []),
            }
        )
        seen.add(sequence_uri)

    for sequence_uri, songs in track_sequences.items():
        if sequence_uri in seen:
            continue
        fallback_label = sequence_uri
        sequences.append({"id": sequence_uri, "presentation": fallback_label, "tracks": songs})

    return sequences


def get_active_device_id(headers: Dict[str, str]) -> Optional[str]:
    response = get(api_base_url + "me/player/devices", headers=headers)
    devices = response.json().get("devices", [])
    for device in devices:
        if device.get("is_active"):
            return device.get("id")
    return None


def get_currently_playing_uri(headers: Dict[str, str]) -> Optional[str]:
    response = get(api_base_url + "me/player/currently-playing", headers=headers)
    if response.status_code == 204:
        return None
    item = response.json().get("item")
    if not item:
        return None
    return item.get("uri")


def add_following_tracks(trigger_uri: str) -> None:
    if not refresh_access_token_if_needed():
        return

    headers = auth_headers()
    device_id = get_active_device_id(headers)
    if not device_id:
        return

    with state_lock:
        continuation_tracks = list(track_sequences.get(trigger_uri, []))

    if not continuation_tracks:
        return

    queue_params = {
        "device_id": device_id,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    for song_uri in continuation_tracks:
        post(api_base_url + "me/player/queue", headers=headers, params={"uri": song_uri}, data=queue_params)

    # Preserve existing behavior: bring continuation tracks to the front by cycling queue.
    currently_playing = trigger_uri
    current_queue: List[str] = []

    while currently_playing == trigger_uri and not stop_event.is_set():
        time.sleep(1)
        currently_playing = get_currently_playing_uri(headers)
        if not currently_playing:
            return

    while currently_playing and currently_playing != continuation_tracks[0] and not stop_event.is_set():
        current_queue.append(currently_playing)
        post(api_base_url + "me/player/next", headers=headers, data=queue_params)
        currently_playing = get_currently_playing_uri(headers)

    for uri in current_queue:
        post(api_base_url + "me/player/queue", headers=headers, params={"uri": uri}, data=queue_params)


def detect_track_worker() -> None:
    while not stop_event.is_set():
        if not refresh_access_token_if_needed():
            time.sleep(2)
            continue

        headers = auth_headers()
        current_uri = get_currently_playing_uri(headers)
        if not current_uri:
            time.sleep(2)
            continue

        should_add_tracks = False
        with state_lock:
            if app_state["current_track"] != current_uri:
                app_state["current_track"] = current_uri
                should_add_tracks = current_uri in track_sequences

        if should_add_tracks:
            add_following_tracks(current_uri)

        time.sleep(2)


track_presentation = load_pickle_file(os.path.join(base_dir, "saved_presentation.p"), [])
track_sequences = load_pickle_file(os.path.join(base_dir, "saved_sequences.p"), {})
link_seq = load_pickle_file(os.path.join(base_dir, "saved_link.p"), {})


def build_auth_url() -> str:
    scope = "user-read-private user-read-email user-read-playback-state user-modify-playback-state user-read-currently-playing"
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": redirect_url,
        "show_dialog": True,
    }
    return f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/auth/login-url")
def login_url():
    return jsonify({"url": build_auth_url()})


@app.get("/login")
def login():
    return redirect(build_auth_url())


@app.get('/callback')
def callback():
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})

    if 'code' in request.args:
        requirements = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_url,
            'client_id': client_id,
            'client_secret': client_secret
        }

        response = post("https://accounts.spotify.com/api/token", data=requirements)
        token_info = response.json()

        if "access_token" not in token_info:
            return jsonify({"error": "Could not retrieve Spotify tokens."}), 400

        app_state["access_token"] = token_info["access_token"]
        app_state["refresh_token"] = token_info.get("refresh_token", "")
        app_state["expires_at"] = datetime.now().timestamp() + token_info.get("expires_in", 3600)
        app_state["current_track"] = ""
        return redirect('/app?connected=1')

    return jsonify({"error": "Missing authorization code."}), 400


@app.get("/api/auth/status")
def auth_status():
    authenticated = is_authenticated() and refresh_access_token_if_needed()
    return jsonify(
        {
            "authenticated": authenticated,
            "expiresAt": app_state.get("expires_at", 0),
            "processingRan": app_state.get("processing_ran", False),
            "selectedSequence": app_state.get("selected_sequence"),
        }
    )


@app.get("/api/sequences")
def list_sequences():
    return jsonify({"sequences": get_sequence_summary()})


@app.post("/api/sequences")
def create_sequence():
    auth_error = auth_error_response()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    song_name = (payload.get("song") or "").strip()
    artist_name = (payload.get("artist") or "").strip()

    if not song_name:
        return jsonify({"error": "Field 'song' is required."}), 400

    headers = auth_headers()
    track = spotify_search_track(song_name, artist_name, headers)
    if track is None:
        return jsonify({"error": "Song not found."}), 404

    sequence_uri = track["uri"]
    label = track["name"]

    with state_lock:
        if sequence_uri in track_sequences:
            return jsonify({"error": "Sequence already exists for this first track."}), 409

        track_sequences[sequence_uri] = []
        unique_label = ensure_unique_presentation_name(label, link_seq)
        track_presentation.append(unique_label)
        link_seq[unique_label] = sequence_uri
        app_state["selected_sequence"] = sequence_uri
        persist_all()

    return jsonify({"sequence": {"id": sequence_uri, "presentation": unique_label, "tracks": []}}), 201


@app.post("/api/sequences/<path:sequence_uri>/tracks")
def extend_sequence(sequence_uri: str):
    auth_error = auth_error_response()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    song_name = (payload.get("song") or "").strip()
    artist_name = (payload.get("artist") or "").strip()

    if not song_name:
        return jsonify({"error": "Field 'song' is required."}), 400

    with state_lock:
        if sequence_uri not in track_sequences:
            return jsonify({"error": "Sequence not found."}), 404

    headers = auth_headers()
    track = spotify_search_track(song_name, artist_name, headers)
    if track is None:
        return jsonify({"error": "Song not found."}), 404

    with state_lock:
        track_sequences[sequence_uri].append(track["uri"])

        current_label = next((label for label, uri in link_seq.items() if uri == sequence_uri), sequence_uri)
        proposed_label = current_label + " -> " + track["name"]
        set_sequence_presentation(sequence_uri, proposed_label)

        app_state["selected_sequence"] = sequence_uri
        persist_all()

        updated_label = next((label for label, uri in link_seq.items() if uri == sequence_uri), sequence_uri)
        updated_tracks = list(track_sequences[sequence_uri])

    return jsonify(
        {
            "sequence": {
                "id": sequence_uri,
                "presentation": updated_label,
                "tracks": updated_tracks,
            }
        }
    )


@app.post("/api/sequences/<path:sequence_uri>/select")
def select_sequence(sequence_uri: str):
    with state_lock:
        if sequence_uri not in track_sequences:
            return jsonify({"error": "Sequence not found."}), 404
        app_state["selected_sequence"] = sequence_uri
    return jsonify({"selectedSequence": sequence_uri})


@app.delete("/api/sequences/<path:sequence_uri>")
def delete_sequence(sequence_uri: str):
    with state_lock:
        if sequence_uri not in track_sequences:
            return jsonify({"error": "Sequence not found."}), 404

        track_sequences.pop(sequence_uri, None)

        labels_to_remove = [label for label, uri in link_seq.items() if uri == sequence_uri]
        for label in labels_to_remove:
            link_seq.pop(label, None)
            if label in track_presentation:
                track_presentation.remove(label)

        if app_state.get("selected_sequence") == sequence_uri:
            app_state["selected_sequence"] = next(iter(track_sequences), None)

        persist_all()

    return jsonify({"deleted": sequence_uri})


@app.get("/api/automation/status")
def automation_status():
    running = automation_thread.is_alive() if automation_thread else False
    return jsonify(
        {
            "running": running,
            "processingRan": app_state.get("processing_ran", False),
        }
    )


@app.post("/api/automation/start")
def start_automation():
    global automation_thread

    auth_error = auth_error_response()
    if auth_error:
        return auth_error

    with state_lock:
        if not track_sequences:
            return jsonify({"error": "At least one sequence is required before starting automation."}), 400

        persist_all()
        app_state["current_track"] = ""
        app_state["processing_ran"] = True

    if automation_thread and automation_thread.is_alive():
        return jsonify({"running": True})

    stop_event.clear()
    automation_thread = Thread(target=detect_track_worker, daemon=True)
    automation_thread.start()
    return jsonify({"running": True})


@app.post("/api/automation/stop")
def stop_automation():
    global automation_thread

    stop_event.set()
    if automation_thread and automation_thread.is_alive():
        automation_thread.join(timeout=5)

    return jsonify({"running": False})


@app.get("/app")
def app_entry():
    if os.path.isdir(react_dist_dir):
        return send_from_directory(react_dist_dir, "index.html")
    return jsonify({"message": "React app is not built yet. Run frontend dev server or build frontend/dist."})


@app.get("/")
def root():
    return redirect("/app")


@app.route("/<path:path>")
def serve_spa(path: str):
    if path.startswith("api/"):
        return jsonify({"error": "API route not found."}), 404

    if os.path.isdir(react_dist_dir):
        target_file = os.path.join(react_dist_dir, path)
        if os.path.exists(target_file) and os.path.isfile(target_file):
            return send_from_directory(react_dist_dir, path)
        return send_from_directory(react_dist_dir, "index.html")

    return jsonify({"message": "React app is not built yet. Run frontend dev server or build frontend/dist."}), 404


# run the program
if __name__ == '__main__':
    print(redirect_url)
    app.run(host="0.0.0.0", port=5001, debug=False)






