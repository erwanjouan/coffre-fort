export function showStatus(statusEl, msg, type) {
  statusEl.textContent = msg
  statusEl.className = type
  setTimeout(() => { statusEl.className = ''; statusEl.textContent = '' }, 3000)
}

export function getOrCreateWrapper(input) {
  if (input.parentElement.classList.contains('pw-wrapper')) return input.parentElement
  const wrapper = document.createElement('div')
  wrapper.className = 'pw-wrapper'
  input.parentNode.insertBefore(wrapper, input)
  wrapper.appendChild(input)
  return wrapper
}

export function getOrCreateActions(wrapper) {
  let actions = wrapper.querySelector('.pw-actions')
  if (!actions) {
    actions = document.createElement('div')
    actions.className = 'pw-actions'
    wrapper.appendChild(actions)
  }
  return actions
}

export function updateInputPadding(wrapper) {
  const actions = wrapper.querySelector('.pw-actions')
  const input = wrapper.querySelector('input')
  if (actions && input) input.style.paddingRight = (actions.offsetWidth + 16) + 'px'
}

export function makeBtn(text, title, onClick) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'pw-toggle'
  btn.textContent = text
  btn.title = title
  btn.addEventListener('click', onClick)
  return btn
}

export function makeDeleteBtn(key, onConfirm) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'pw-toggle ms-auto'
  btn.style.color = '#f87171'
  btn.textContent = '✕'
  btn.title = `Remove "${key}"`
  btn.addEventListener('click', (e) => {
    e.stopPropagation()
    if (!confirm(`Remove "${key}"?`)) return
    onConfirm()
  })
  return btn
}
