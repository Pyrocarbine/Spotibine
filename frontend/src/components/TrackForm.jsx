import { useState } from "react";

export default function TrackForm({ title, submitText, onSubmit }) {
  const [song, setSong] = useState("");
  const [artist, setArtist] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    await onSubmit(song.trim(), artist.trim());
    setSong("");
    setArtist("");
  }

  return (
    <form className="track-form" onSubmit={handleSubmit}>
      <h3>{title}</h3>
      <label>
        Song name
        <input value={song} onChange={(event) => setSong(event.target.value)} required />
      </label>
      <label>
        Artist
        <input value={artist} onChange={(event) => setArtist(event.target.value)} />
      </label>
      <button type="submit" className="primary-button">
        {submitText}
      </button>
    </form>
  );
}
