### Description

    Many songs are meant to be played together, including Brain Damage/Eclipse, Golden Slumbers/Carry That Weight/The End.
    The program here will allow the user to automate song successions.

#### How It Works

    This program uses the Spotify API, so to use it the user must create their own Spotify API app to gain access to a client ID and a client secret.
    Once the client_id and client_secret is provided in a .env file, the user can run main.py.

    When the first track in a sequence is played, the program will add the following songs in queue.
    If there are songs previously in queue, the program will skip tracks until a track in the automated song sequence is found.
    However the original queue will stay and play after the sequence is finished.

    The program is best used in playlist shuffle mode, with the first song of a sequence being in the playlist.
