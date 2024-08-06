### Description
Many songs are meant to be played together, including Brain Damage/Eclipse, Golden Slumbers/Carry That Weight/The End.
The program here will allow the user to automate these successions when using spotify on the web.

### How It Works
This program uses the Spotify Web API, and the user must create their own Spotify API app to gain access to a client ID and a client secret required for the program.
You can create one from the dashboard at [Spotify for Developers](https://developer.spotify.com/dashboard) (an account is required). Please set redirect url to "http://localhost:5000/callback" and indicate Web API is being used
 
Once the client_id and client_secret are provided in a .env file, the user can run main.py.
    
When the first track in a sequence is played, the program will add the following songs to the queue.
If there are songs previously in the queue, the program will skip tracks until a track in the automated song sequence is found.
However, the original queue will stay and play after finishing the sequence.
    
The program is best used in playlist shuffle mode, with the first song of a sequence being in the playlist.
