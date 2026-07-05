export async function getFillData(clientId) {
  const res = await fetch(`/api/clients/${clientId}/fill-data`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Could not load fill data')
  return data
}

// Queue a client for a running Claude Code filler session to auto-fill (no paste).
export async function enqueueFill(clientId) {
  const res = await fetch('/api/fill-request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Could not queue fill request')
  return data
}

export async function getFillQueue() {
  const res = await fetch('/api/fill-requests')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Could not load queue')
  return data.requests || []
}

// Remove/cancel a single job (any status).
export async function removeFillJob(jobId) {
  const res = await fetch(`/api/fill-request/${jobId}`, { method: 'DELETE' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Could not remove job')
  return data.requests || []
}

// Clear the queue: scope 'finished' (done/error) or 'all'.
export async function clearFillQueue(scope = 'finished') {
  const res = await fetch(`/api/fill-requests/clear?scope=${scope}`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Could not clear queue')
  return data.requests || []
}
