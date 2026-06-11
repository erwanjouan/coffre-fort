/**
 * Fetch the secrets file from the server as raw YAML text.
 *
 * `fetch` is the browser's built-in way to make HTTP requests.  The
 * `await` keyword pauses execution here until the server responds, which
 * makes the code read like normal top-to-bottom code even though the
 * network call happens asynchronously in the background.
 *
 * @returns {Promise<string>} The full YAML content of the secrets file.
 * @throws  {Error}          If the server returns an error status.
 */
export async function loadYaml() {
  const res = await fetch('/api/yaml')
  if (!res.ok) throw new Error('Failed to load secrets')
  return res.text()
}

/**
 * Send updated YAML text to the server to be encrypted and saved to disk.
 *
 * We POST the YAML as plain text in the request body.  The server validates
 * it, backs up the previous file, re-encrypts the new content, and writes
 * it to disk.  If the YAML is invalid the server returns a 4xx status and
 * we throw an error so the editor can show the message to the user.
 *
 * @param {string} text - The full YAML content to save.
 * @returns {Promise<void>}
 * @throws  {Error}      If the server rejects the content or fails to save.
 */
export async function saveYaml(text) {
  const res = await fetch('/api/yaml', {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    body: text
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.error || 'Save failed')
  }
}
