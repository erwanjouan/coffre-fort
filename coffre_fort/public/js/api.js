export async function loadSecrets() {
  const res = await fetch('/api/secrets')
  if (!res.ok) throw new Error('Failed to load secrets')
  return res.json()
}

export async function loadSchema() {
  const res = await fetch('/api/schema')
  if (!res.ok) throw new Error('Failed to load schema')
  return res.json()
}

export async function saveSecrets(data) {
  const res = await fetch('/api/secrets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.error || 'Save failed')
  }
}
