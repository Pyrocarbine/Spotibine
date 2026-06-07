import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import {
  createSequence,
  deleteSequence,
  extendSequence,
  getAuthStatus,
  getAutomationStatus,
  getSequences,
  selectSequence,
  startAutomation,
  stopAutomation
} from "./api/client";
import SequenceList from "./components/SequenceList";
import TrackForm from "./components/TrackForm";

function Dashboard() {
  const [auth, setAuth] = useState({ authenticated: false, selectedSequence: null });
  const [sequences, setSequences] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const selectedSequence = useMemo(
    () => sequences.find((sequence) => sequence.id === auth.selectedSequence) ?? null,
    [sequences, auth.selectedSequence]
  );

  async function refreshState() {
    const [authStatus, sequenceData, automationData] = await Promise.all([
      getAuthStatus(),
      getSequences(),
      getAutomationStatus()
    ]);

    const fallbackSelected = sequenceData.sequences[0]?.id ?? null;
    setAuth({
      authenticated: authStatus.authenticated,
      selectedSequence: authStatus.selectedSequence ?? fallbackSelected
    });
    setSequences(sequenceData.sequences);
    setIsRunning(Boolean(automationData.running));
  }

  useEffect(() => {
    let active = true;
    async function initialize() {
      setIsLoading(true);
      setMessage("");
      try {
        await refreshState();
      } catch (error) {
        if (active) {
          setMessage(error.message);
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }
    initialize();

    return () => {
      active = false;
    };
  }, []);

  async function withRefresh(action, successMessage) {
    setMessage("");
    try {
      await action();
      await refreshState();
      if (successMessage) {
        setMessage(successMessage);
      }
    } catch (error) {
      setMessage(error.message);
    }
  }

  if (isLoading) {
    return <p className="muted">Loading…</p>;
  }

  return (
    <main className="container">
      <header className="header">
        <h1>Spotibine</h1>
        <p className="muted">React frontend with Flask API endpoints.</p>
      </header>

      {!auth.authenticated ? (
        <section className="card">
          <h2>Spotify connection required</h2>
          <p>Connect your Spotify account to start creating sequence rules.</p>
          <a className="primary-button login-link" href="/login">
            Login with Spotify
          </a>
        </section>
      ) : (
        <>
          <section className="card">
            <h2>Saved Sequences</h2>
            <SequenceList
              sequences={sequences}
              selectedId={auth.selectedSequence}
              onSelect={(sequenceId) =>
                withRefresh(() => selectSequence(sequenceId), "Sequence selected.")
              }
              onDelete={(sequenceId) =>
                withRefresh(() => deleteSequence(sequenceId), "Sequence deleted.")
              }
            />
          </section>

          <section className="forms-grid">
            <section className="card">
              <TrackForm
                title="Create new sequence"
                submitText="Add first track"
                onSubmit={(song, artist) =>
                  withRefresh(() => createSequence(song, artist), "Sequence created.")
                }
              />
            </section>

            <section className="card">
              <TrackForm
                title={
                  selectedSequence
                    ? `Extend selected sequence (${selectedSequence.presentation})`
                    : "Select a sequence to extend"
                }
                submitText="Add continuation"
                onSubmit={(song, artist) => {
                  if (!auth.selectedSequence) {
                    throw new Error("Please select a sequence first.");
                  }
                  return withRefresh(
                    () => extendSequence(auth.selectedSequence, song, artist),
                    "Sequence extended."
                  );
                }}
              />
            </section>
          </section>

          <section className="card">
            <h2>Automation</h2>
            <p>
              Status: <strong>{isRunning ? "Running" : "Stopped"}</strong>
            </p>
            <div className="actions">
              <button
                className="primary-button"
                disabled={isRunning}
                onClick={() => withRefresh(() => startAutomation(), "Automation started.")}
              >
                Start automation
              </button>
              <button
                className="danger-button"
                disabled={!isRunning}
                onClick={() => withRefresh(() => stopAutomation(), "Automation stopped.")}
              >
                Stop automation
              </button>
            </div>
          </section>
        </>
      )}

      {message && <p className="message">{message}</p>}
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/app" replace />} />
      <Route path="/app" element={<Dashboard />} />
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  );
}
