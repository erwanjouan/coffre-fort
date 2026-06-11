import { getOrCreateWrapper, getOrCreateActions, updateInputPadding, makeBtn, makeDeleteBtn } from './ui.js'

export function applyDeleteButtons(root, editor, onDelete) {
  if (!editor) return
  const catKeys = new Set(Object.keys(editor.getValue()))
  root.querySelectorAll('.jedi-editor-legend.card-header').forEach(header => {
    if (header.dataset.deleteBtn) return
    const text = header.childNodes[0]?.textContent?.trim()
    if (!text || !catKeys.has(text)) return
    header.dataset.deleteBtn = 'true'
    header.appendChild(makeDeleteBtn(text, () => {
      const d = editor.getValue()
      delete d[text]
      editor.setValue(d)
      onDelete()
    }))
  })
}

export function applyUrlButtons(root) {
  root.querySelectorAll('label').forEach(label => {
    if (label.textContent.trim() !== 'URL') return
    const input = document.getElementById(label.htmlFor)
    if (!input || input.dataset.urlBtn) return
    input.dataset.urlBtn = 'true'
    const wrapper = getOrCreateWrapper(input)
    const actions = getOrCreateActions(wrapper)
    actions.appendChild(makeBtn('↗', 'Open URL', () => {
      if (input.value) window.open(input.value, '_blank', 'noopener')
    }))
    updateInputPadding(wrapper)
  })
}

export function applyPasswordToggles(root) {
  root.querySelectorAll('label').forEach(label => {
    if (label.textContent.trim() !== 'Password') return
    const input = document.getElementById(label.htmlFor)
    if (!input || input.dataset.pwToggled) return
    input.type = 'password'
    input.dataset.pwToggled = 'true'
    const wrapper = getOrCreateWrapper(input)
    const actions = getOrCreateActions(wrapper)
    const btn = makeBtn('Show', 'Toggle visibility', () => {
      const hidden = input.type === 'password'
      input.type = hidden ? 'text' : 'password'
      btn.textContent = hidden ? 'Hide' : 'Show'
    })
    actions.appendChild(btn)
    updateInputPadding(wrapper)
  })
}

export function applyCopyButtons(root) {
  root.querySelectorAll('label').forEach(label => {
    const title = label.textContent.trim()
    if (title !== 'Login' && title !== 'Password') return
    const input = document.getElementById(label.htmlFor)
    if (!input || input.dataset.copyBtn) return
    input.dataset.copyBtn = 'true'
    const wrapper = getOrCreateWrapper(input)
    const actions = getOrCreateActions(wrapper)
    const btn = makeBtn('Copy', 'Copy to clipboard', async () => {
      await navigator.clipboard.writeText(input.value)
      const prev = btn.textContent
      btn.textContent = '✓'
      setTimeout(() => { btn.textContent = prev }, 1500)
    })
    actions.appendChild(btn)
    updateInputPadding(wrapper)
  })
}
