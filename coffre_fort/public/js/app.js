import { loadSecrets, loadSchema, saveSecrets } from './api.js'
import { showStatus } from './ui.js'
import { applyDeleteButtons, applyUrlButtons, applyPasswordToggles, applyCopyButtons } from './enhancements.js'

const btnSave = document.getElementById('btn-save')
const statusEl = document.getElementById('status')
let editor = null

async function init() {
  const [data, schema] = await Promise.all([loadSecrets(), loadSchema()])

  const categorySchema = schema.additionalProperties
  const properties = {}
  for (const catKey of Object.keys(data)) {
    properties[catKey] = { ...categorySchema, title: catKey }
  }
  const fullSchema = { ...schema, properties, additionalProperties: categorySchema }

  editor = new Jedison.Create({
    container: document.querySelector('#jedison-root'),
    theme: new Jedison.ThemeBootstrap5(),
    iconLib: 'fontawesome6',
    btnContents: false,
    schema: fullSchema,
    data
  })

  editor.on('change', () => {
    btnSave.disabled = false
  })

  const root = document.querySelector('#jedison-root')

  function applyAll() {
    applyDeleteButtons(root, editor, () => { btnSave.disabled = false })
    applyPasswordToggles(root)
    applyCopyButtons(root)
    applyUrlButtons(root)
  }

  applyAll()
  new MutationObserver(applyAll).observe(root, { childList: true, subtree: true })

  btnSave.addEventListener('click', async () => {
    btnSave.disabled = true
    try {
      await saveSecrets(editor.getValue())
      showStatus(statusEl, 'Saved', 'ok')
    } catch (err) {
      showStatus(statusEl, err.message, 'err')
      btnSave.disabled = false
    }
  })
}

init().catch(err => {
  document.getElementById('jedison-root').textContent = 'Error: ' + err.message
})
