from dotenv import load_dotenv
import os
import base64
from requests import post, get
import json
import urllib.parse
from flask import Flask, redirect, request, jsonify, render_template, url_for
from datetime import datetime, timedelta
import time
# import for loading a html webpage while the api is running
from threading import Thread


load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_url = "http://localhost:5000/callback"

session = {}
"""
def get_token():
    auth_string = client_id + ":" + client_secret
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}
    result = post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result["access_token"]
    return token
def get_auth_header(token):
    return {"Authorization": "Bearer " + token}

def search_for_artist(token, artist_name):
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    query = f"?q={artist_name}&type=artist&limit=1"

    query_url = url + query
    result = get(query_url, headers=headers)
    json_result = json.loads(result.content)["artists"]["items"]
    if len(json_result) == 0:
        print("No artists available")
        return None
    else:
        return json_result[0]

def get_songs_by_artist(token,artist_id):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?country=US"
    headers = get_auth_header(token)
    result = get(url, headers=headers)
    json_result = json.loads(result.content)["tracks"]
    return json_result
token = get_token()
result = search_for_artist(token,"Michael Jackson")
artist_id = result["id"]
songs = get_songs_by_artist(token,artist_id)

for idx, song in enumerate(songs):
    print(f"{idx + 1}.{song['name']}")
"""



app = Flask(__name__)
app.secret_key = "53d335f8-571a-4590-a310-1f9579440851"
api_base_url = "https://api.spotify.com/v1/"


# stores the sequences of songs we have
track_sequences = {}
# use track presentation to show tracks in HTML file
track_presentation = []
# link track_sequences and track_presentation
link_seq = {}

@app.route('/')
def index():
    return "Welcome to my Spotify App <a href='/login'>Login With Spotify</a>"

@app.route('/login')
def login():
    scope = "user-read-private user-read-email user-read-playback-state user-modify-playback-state user-read-currently-playing"

    params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': redirect_url,
        'show_dialog': True
    }

    auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)

@app.route('/callback')
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

        response = post("https://accounts.spotify.com/api/token",data=requirements)
        token_info = response.json()

        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['expires_at'] = datetime.now().timestamp() + token_info['expires_in']
        session['current_track'] = ""

        return redirect('/find-track')


"""
@app.route('/playlists')
def get_playlists():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        redirect('/refresh-token')

    headers = {
        "Authorization": "Bearer " + session['access_token']
    }
    response = get(api_base_url + 'me/playlists', headers=headers)
    playlists = response.json()

    return jsonify(playlists)
"""


@app.route('/refresh-token')
def refresh_token():
    """
    if 'refresh_token' not in session:
        return redirect('/login')
    """

    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            'grant_type': "refresh_token",
            'refresh_token': session['refresh_token'],
            'client_id': client_id,
            'client_secret': client_secret
        }

        response = post("https://accounts.spotify.com/api/token", data=req_body)
        new_token_info = response.json()

        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']
        return "token updated"


@app.route('/refresh')
def refresh_info():
    if datetime.now().timestamp() + 3600 > session['expires_at']:
        refresh_token()


@app.route('/get-Authorization')
def find_auth():
    refresh_info()
    return {"Authorization": "Bearer " + session['access_token']}


@app.route('/find-device')
def find_device():
    refresh_info()
    headers = find_auth()

    response = get(api_base_url + 'me/player/devices', headers=headers)
    encoded = response.json()

    for items in encoded['devices']:
        if items['is_active']:
            session['active_device'] = items["id"]
            return redirect("/find-track")
    return redirect("/find-track")


"""
track_sequences = {
    # Golden Slumbers -> Carry that Weight -> The End
    "spotify:track:01SfTM5nfCou5gQL70r6gs": ["spotify:track:5eZrW59C3UgBhkqNlowEID","spotify:track:5aHHf6jrqDRb1fcBmue2kn"],
    # Brain Damage -> Eclipse
    "spotify:track:05uGBKRCuePsf43Hfm0JwX": ["spotify:track:1tDWVeCR9oWGX8d5J9rswk"],
    # We Will Rock You -> We Are The Champions
    "spotify:track:3bCjss1Y0kPPaSgd9cb89K": ["spotify:track:6ceLJHWkvMM3oc0Ftodrdm"]
}
"""

# Ask the user for the first track in the series
@app.route('/find-track', methods=["POST","GET"])
def find_first_track():
    refresh_info()
    headers = find_auth()
    if request.method == "POST":
        new_song = request.form["Leading_song"]
        the_artist = request.form["Leading_artist"]
        if new_song == 'finished' or new_song == 'done':
            return track_sequences
        first_response = get(api_base_url + 'search' + f'?q={new_song} artist:{the_artist}&type=track&limit=1', headers=headers)
        first_encoded = first_response.json()['tracks']['items'][0]['uri']
        session['first_track'] = first_encoded
        track_sequences[session['first_track']] = []
        # update track presentation
        track_presentation.append(first_response.json()['tracks']['items'][0]['name'])
        return redirect('/find-next-track')
    else:
        return render_template("Track_inputs.html")


# Ask for the following tracks
@app.route('/find-next-track', methods=["POST", "GET"])
def find_next_track():
    refresh_info()
    headers = find_auth()
    if request.method == "POST":
        next_track = request.form["following_song"]
        next_artist = request.form["following_artist"]
        second_response = get(api_base_url + 'search' + f'?q={next_track} artist:{next_artist}&type=track&limit=1',
                              headers=headers)
        second_encoded = second_response.json()['tracks']['items'][0]
        track_sequences[session['first_track']].append(second_encoded['uri'])
        track_presentation[-1] += " -> "
        track_presentation[-1] += second_encoded['name']
        # link track_sequence and track_presentation
        link_seq[track_presentation[-1]] = session['first_track']
        return redirect('/ask-user-for-more')
    else:
        return render_template("Track_continuations.html")


# Ask the user if there are more tracks in the continuation
@app.route('/ask-user-for-more', methods=["POST", "GET"])
def ask_user_for_more():
    if request.method == "POST":
        next_track = request.form
    else:
        return render_template("Ask_for_New_song.html", data=track_presentation)

    if 'submit' in request.form:
        if next_track['submit'] == "Stop":
            return redirect('/processing')
        elif next_track['submit'] == "Add New Sequence":
            return redirect('/find-track')
    for item in track_presentation:
        if item in request.form and request.form[item] == "Delete sequence":
            delete_seq = link_seq[item]
            track_sequences.pop(delete_seq)
            track_presentation.remove(item)
            return redirect('/ask-user-for-more')
        elif item in request.form and request.form[item] == "Add New Song":
            track_presentation.remove(item)
            track_presentation.append(item)
            session['first_track'] = link_seq[item]
            return redirect('find-next-track')


# Ask the user if there are more tracks in the continuation
@app.route('/ask-user-for-more-second-version', methods=["POST", "GET"])
def ask_user_for_more_second_version():
    if request.method == "POST":
        next_track = request.form
    else:
        return render_template("Ask_for_New_song.html", data=track_presentation)
    if 'submit' in request.form:
        if next_track['submit'] == "Add New Song to Existing Sequence":
            return redirect('/find-next-track')
        elif next_track['submit'] == "Stop":
            return redirect('/processing')
        elif next_track['submit'] == "Add New Sequence":
            return redirect('/find-track')
    for item in track_presentation:
        if item in request.form and request.form[item] == "Delete sequence":
            delete_seq = link_seq[item]
            track_sequences.pop(delete_seq)
            track_presentation.remove(item)
            return redirect('/ask-user-for-more-second-version')


@app.route('/processing')
def processing():
    # run application by calling detect_track
    session['current-track'] = ""
    thr = Thread(target=detect_track)
    thr.start()
    return redirect('/main-page')


@app.route('/main-page', methods=['POST', 'GET'])
def main_page():
    if request.method == "POST":
        if 'submit' in request.form and request.form['submit'] == 'Request New Song Sequence':
            return redirect('/find-track')
        else:
            for item in track_presentation:
                if item in request.form and request.form[item] == "Delete sequence":
                    delete_seq = link_seq[item]
                    track_sequences.pop(delete_seq)
                    track_presentation.remove(item)
                    return redirect('/main-page')
    else:
        return render_template("Loading_page.html", data=track_presentation)


@app.route('/detect-track')
def detect_track():
    while True:
        refresh_info()
        headers = find_auth()

        response = get(api_base_url + 'me/player/currently-playing', headers=headers)
        if response.status_code == 204:
            time.sleep(10)
            continue
        encoded = response.json()

        if session['current-track'] != encoded['item']['uri']:
            session['current-track'] = encoded['item']['uri']

            if session['current-track'] in track_sequences:
                add_track()
        time.sleep(10)


def add_track():
    refresh_info()
    headers = find_auth()
    find_device()

    requirements = {
        'device_id': session['active_device'],
        'client_id': client_id,
        'client_secret': client_secret
    }

    for song in track_sequences[session['current-track']]:
        post(api_base_url + "me/player/queue" + "?uri=" + song, headers=headers, data=requirements)


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=False)









