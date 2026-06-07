const jsonHeaders = {
  "Content-Type": "application/json"
};

async function handleResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.error || "Request failed.";
    throw new Error(message);
  }
  return payload;
}

export async function getAuthStatus() {
  const response = await fetch("/api/auth/status");
  return handleResponse(response);
}

export async function getSequences() {
  const response = await fetch("/api/sequences");
  return handleResponse(response);
}

export async function createSequence(song, artist) {
  const response = await fetch("/api/sequences", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ song, artist })
  });
  return handleResponse(response);
}

export async function extendSequence(sequenceId, song, artist) {
  const response = await fetch(`/api/sequences/${encodeURIComponent(sequenceId)}/tracks`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ song, artist })
  });
  return handleResponse(response);
}

export async function selectSequence(sequenceId) {
  const response = await fetch(`/api/sequences/${encodeURIComponent(sequenceId)}/select`, {
    method: "POST"
  });
  return handleResponse(response);
}

export async function deleteSequence(sequenceId) {
  const response = await fetch(`/api/sequences/${encodeURIComponent(sequenceId)}`, {
    method: "DELETE"
  });
  return handleResponse(response);
}

export async function getAutomationStatus() {
  const response = await fetch("/api/automation/status");
  return handleResponse(response);
}

export async function startAutomation() {
  const response = await fetch("/api/automation/start", {
    method: "POST"
  });
  return handleResponse(response);
}

export async function stopAutomation() {
  const response = await fetch("/api/automation/stop", {
    method: "POST"
  });
  return handleResponse(response);
}
