import { loadYaml, saveYaml } from './api.js'

const btnSave = document.getElementById('btn-save')
const statusEl = document.getElementById('status')

/**
 * Briefly display a status message (e.g. "Saved" or an error) in the header.
 *
 * We set the text and a CSS class that controls the colour, then use
 * setTimeout to clear both after 3 seconds so the message disappears on
 * its own without the user having to dismiss it.
 *
 * @param {string} msg  - The text to display (e.g. "Saved" or "invalid YAML").
 * @param {string} type - Either "ok" (green) or "err" (red), matching CSS classes.
 */
function showStatus(msg, type) {
  statusEl.textContent = msg
  statusEl.className = type
  setTimeout(() => { statusEl.className = ''; statusEl.textContent = '' }, 3000)
}

/**
 * Initialise the page: load the YAML from the server and create the editor.
 *
 * This function runs once when the page loads.  It:
 * 1. Fetches the current YAML content from the server.
 * 2. Creates a CodeMirror editor inside the #editor-container div, pre-filled
 *    with that content and configured for YAML syntax highlighting.
 * 3. Enables the Save button whenever the user changes anything.
 * 4. Wires up the Save button to send the updated content back to the server.
 *
 * It is declared `async` because it uses `await` to wait for the network
 * request before creating the editor.
 */
async function init() {
  const content = await loadYaml()

  // CodeMirror is loaded as a global script tag in index.html, so `CodeMirror`
  // is available here as a global variable (no import needed).
  const editor = CodeMirror(document.getElementById('editor-container'), {
    value: content,       // pre-fill the editor with the loaded YAML
    mode: 'yaml',         // enable YAML syntax highlighting
    theme: 'dracula',     // dark colour theme
    lineNumbers: true,    // show line numbers on the left
    tabSize: 2,           // indent with 2 spaces (YAML convention)
    indentWithTabs: false,
    lineWrapping: false,
    autofocus: true,      // place the cursor in the editor immediately
  })

  // Enable the Save button as soon as any change is made.
  editor.on('change', () => { btnSave.disabled = false })

  /**
   * Send the current editor content to the server and update the status bar.
   *
   * This is called when the user clicks Save.  We disable the button first so
   * it cannot be clicked twice in a row, then attempt the save.  If it fails
   * we re-enable the button so the user can try again.
   */
  async function doSave() {
    btnSave.disabled = true
    try {
      await saveYaml(editor.getValue())
      showStatus('Saved', 'ok')
    } catch (err) {
      showStatus(err.message, 'err')
      btnSave.disabled = false
    }
  }

  btnSave.addEventListener('click', doSave)
}

// Start the initialisation and catch any unexpected errors (e.g. network down)
// by showing a plain-text message in the editor area instead of a silent blank page.
init().catch(err => {
  document.getElementById('editor-container').textContent = 'Error: ' + err.message
})
