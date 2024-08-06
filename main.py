from dotenv import load_dotenv
import os
from requests import post, get
import urllib.parse
from flask import Flask, redirect, request, jsonify, render_template
from datetime import datetime
import time
# import for loading a html webpage while the api is running
import threading
import pickle

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_url = "http://localhost:5000/callback"

session = {}

app = Flask(__name__)
app.secret_key = "53d335f8-571a-4590-a310-1f9579440851"
api_base_url = "https://api.spotify.com/v1/"


# use track presentation to show tracks in HTML file
track_presentation = []
open("saved_presentation.p", "ab")
if os.path.getsize("saved_presentation.p") > 0:
    with open("saved_presentation.p", "rb") as f:
        track_presentation = pickle.load(f)
# stores the sequences of songs we have
track_sequences = {}
open("saved_sequences.p", "ab")
if os.path.getsize("saved_sequences.p") > 0:
    with open("saved_sequences.p", "rb") as f:
        track_sequences = pickle.load(f)
# link track_sequences and track_presentation
link_seq = {}
open("saved_link.p", "ab")
if os.path.getsize("saved_link.p") > 0:
    with open("saved_link.p", "rb") as f:
        link_seq = pickle.load(f)
# if this is true, then '/processing has not been run yet'
session['processing-ran'] = False


# First Page
@app.route('/')
def index():
    if 'access_token' not in session:
        return ("<h3> Welcome to my Spotify App. </h3>" 
                "<p> To begin, we will like request some permissions for your Spotify Account "
                "<br><br> Please <a href='/login'>Login With Spotify</a></p>")
    else:
        if session['processing-ran']:
            return redirect("/main-page")
        else:
            return redirect('/ask-user-for-more')


# Redirects to login page
@app.route('/login')
def login():
    scope = "user-read-private user-read-email user-read-playback-state user-modify-playback-state user-read-currently-playing"

    # Dictionary required for authorization
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': redirect_url,
        'show_dialog': True
    }

    auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)


# gives us important values such as access token and refresh token
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

        return redirect('/ask-user-for-more')


# update access token
@app.route('/refresh-token')
def refresh_token():
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


# used to check if access token expired
@app.route('/refresh')
def refresh_info():
    if datetime.now().timestamp() + 3600 > session['expires_at']:
        refresh_token()


# give authorization token, required for many get() functions that informs us
@app.route('/get-Authorization')
def find_auth():
    refresh_info()
    return {"Authorization": "Bearer " + session['access_token']}


# track the device id of the active device
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
        first_encoded = first_response.json()['tracks']['items']
        if len(first_encoded) == 0:
            # if song is not found then send a error message
            return render_template("Track_inputs.html", data=1)
        if first_encoded[0]['uri'] in track_sequences:
            return render_template("Track_inputs.html", data=2)
        session['first_track'] = first_encoded[0]['uri']
        track_sequences[session['first_track']] = []
        # update track presentation
        track_presentation.append(first_response.json()['tracks']['items'][0]['name'])
        link_seq[track_presentation[-1]] = session['first_track']
        return redirect('/find-next-track')
    else:
        return render_template("Track_inputs.html",data=0)


# Ask for the following tracks
@app.route('/find-next-track', methods=["POST", "GET"])
def find_next_track():
    refresh_info()
    headers = find_auth()
    current_sequence_and_error_found = [track_presentation[-1], 0]
    if request.method == "POST":
        next_track = request.form["following_song"]
        next_artist = request.form["following_artist"]
        second_response = get(api_base_url + 'search' + f'?q={next_track} artist:{next_artist}&type=track&limit=1',
                              headers=headers)
        second_encoded = second_response.json()['tracks']['items']
        if len(second_encoded) == 0:
            current_sequence_and_error_found[1] = 1
            return render_template("Track_continuations.html", data=current_sequence_and_error_found)
        track_sequences[session['first_track']].append(second_encoded[0]['uri'])
        link_seq.pop(track_presentation[-1])
        track_presentation[-1] += " -> "
        track_presentation[-1] += second_encoded[0]['name']
        # link track_sequence and track_presentation
        link_seq[track_presentation[-1]] = session['first_track']
        return redirect('/ask-user-for-more')
    else:
        return render_template("Track_continuations.html", data=current_sequence_and_error_found)


# Ask the user if there are more tracks in the continuation
@app.route('/ask-user-for-more', methods=["POST", "GET"])
def ask_user_for_more():
    if request.method == "POST":
        next_track = request.form
    else:
        return render_template("Ask_for_New_song.html", data=track_presentation)

    if 'submit' in request.form:
        # if Stop is pressed, activate the auto queue system
        if next_track['submit'] == "Save and Launch Automation!":
            return redirect('/processing')
        elif next_track['submit'] == "Add New Sequence":
            return redirect('/find-track')
    for item in track_presentation:
        f = open("song_sequences.txt", "wt")
        # if a sequence is deleted, we must remove that from the track_sequences and track_presentation
        if item in request.form and request.form[item] == "Delete sequence":
            delete_seq = link_seq[item]
            track_sequences.pop(delete_seq)
            track_presentation.remove(item)
            return redirect('/ask-user-for-more')
        # if user requests an additional song for a sequence, then redirect to find-next-track
        elif item in request.form and request.form[item] == "Add New Song":
            # remove() and append() used to place the sequence last
            track_presentation.remove(item)
            track_presentation.append(item)
            session['first_track'] = link_seq[item]
            return redirect('find-next-track')


# if a first song in a sequence is detected, then call add_track()
@app.route('/detect-track')
def detect_track():
    while not session['stop-thread']:
        refresh_info()
        headers = find_auth()

        response = get(api_base_url + 'me/player/currently-playing', headers=headers)
        if response.status_code == 204:
            time.sleep(2)
            continue
        encoded = response.json()

        if session['started'] and session['previous-track'] == encoded['item']['uri']:
            time.sleep(2)
            continue
        if session['current-track'] != encoded['item']['uri']:
            session['current-track'] = encoded['item']['uri']

            if session['current-track'] in track_sequences:
                add_track()
        time.sleep(2)


# add_track put the following tracks into the queue
def add_track():
    refresh_info()
    headers = find_auth()
    find_device()

    requirements = {
        'device_id': session['active_device'],
        'client_id': client_id,
        'client_secret': client_secret
    }
    encoded = get(api_base_url + 'me/player/currently-playing', headers=headers).json()['item']['uri']
    current_queue = []
    for song in track_sequences[session['current-track']]:
        post(api_base_url + "me/player/queue" + "?uri=" + song, headers=headers, data=requirements)
    while encoded == session['current-track']:
        if session['stop-thread']:
            return
        time.sleep(1)
        encoded = get(api_base_url + 'me/player/currently-playing', headers=headers).json()
        if not encoded['item']:
            break
        encoded = encoded['item']['uri']
    while encoded != track_sequences[session['current-track']][0]:
        current_queue.append(encoded)
        # skip to next track in queue
        post(api_base_url + "me/player/next", headers=headers, data=requirements)
        encoded = get(api_base_url + 'me/player/currently-playing', headers=headers).json()
        if not encoded['item']:
            break
        encoded = encoded['item']['uri']
    for uri in current_queue:
        post(api_base_url + "me/player/queue" + "?uri=" + uri, headers=headers, data=requirements)


thr = threading.Thread()
session['started'] = False


# create a thread that will run a process, while our main program is displaying an HTML file
@app.route('/processing')
def processing():
    # run application by calling detect_track
    session['current-track'] = ""
    session['stop-thread'] = False

    # Store all files
    os.remove("saved_link.p")
    link_file = open("saved_link.p","wb")
    pickle.dump(link_seq, link_file)
    link_file.close()

    os.remove("saved_presentation.p")
    link_file = open("saved_presentation.p", "wb")
    pickle.dump(track_presentation, link_file)
    link_file.close()

    os.remove("saved_sequences.p")
    link_file = open("saved_sequences.p", "wb")
    pickle.dump(track_sequences, link_file)
    link_file.close()

    global thr
    thr = threading.Thread(target=detect_track)
    thr.start()
    return redirect('/main-page')


# the main page will continue displaying our track sequences, the user can still add or delete sequence
@app.route('/main-page', methods=['POST', 'GET'])
def main_page():
    if request.method == "POST":
        headers = find_auth()
        session['started'] = True
        session['previous-track'] = get(api_base_url + 'me/player/currently-playing', headers=headers).json()['item']
        if session['previous-track']:
            session['previous-track'] = session['previous-track']['uri']
        session['stop-thread'] = True
        thr.join()
        if 'submit' in request.form and request.form['submit'] == 'Request New Song Sequence':
            return redirect('/find-track')
        else:
            for item in track_presentation:
                if item in request.form and request.form[item] == "Delete sequence":
                    delete_seq = link_seq[item]
                    track_sequences.pop(delete_seq)
                    track_presentation.remove(item)
                    return redirect('/processing')
    else:
        return render_template("Loading_page.html", data=track_presentation)


# run the program
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=False)









