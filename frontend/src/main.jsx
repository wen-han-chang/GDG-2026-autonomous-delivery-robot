import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

const originalFetch = window.fetch.bind(window)
let handlingSessionExpired = false

function showSessionExpiredDialog(message) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div')
    overlay.style.position = 'fixed'
    overlay.style.inset = '0'
    overlay.style.background = 'rgba(0, 0, 0, 0.45)'
    overlay.style.display = 'flex'
    overlay.style.alignItems = 'center'
    overlay.style.justifyContent = 'center'
    overlay.style.zIndex = '99999'

    const modal = document.createElement('div')
    modal.style.width = 'min(92vw, 420px)'
    modal.style.background = '#ffffff'
    modal.style.color = '#111111'
    modal.style.border = '1px solid #e5e7eb'
    modal.style.borderRadius = '16px'
    modal.style.boxShadow = '0 12px 32px rgba(0,0,0,0.35)'
    modal.style.padding = '20px 20px 16px'

    const title = document.createElement('h3')
    title.textContent = '通知'
    title.style.margin = '0 0 10px 0'
    title.style.fontSize = '20px'

    const content = document.createElement('p')
    content.textContent = message
    content.style.margin = '0 0 18px 0'
    content.style.fontSize = '18px'

    const actions = document.createElement('div')
    actions.style.display = 'flex'
    actions.style.justifyContent = 'flex-end'

    const okBtn = document.createElement('button')
    okBtn.type = 'button'
    okBtn.textContent = 'OK'
    okBtn.style.background = '#f97316'
    okBtn.style.border = '1px solid #ea580c'
    okBtn.style.color = '#ffffff'
    okBtn.style.borderRadius = '999px'
    okBtn.style.padding = '8px 18px'
    okBtn.style.fontWeight = '700'
    okBtn.style.cursor = 'pointer'

    okBtn.addEventListener('click', () => {
      overlay.remove()
      resolve()
    })

    actions.appendChild(okBtn)
    modal.appendChild(title)
    modal.appendChild(content)
    modal.appendChild(actions)
    overlay.appendChild(modal)
    document.body.appendChild(overlay)
  })
}

window.fetch = async (...args) => {
  const response = await originalFetch(...args)

  const input = args[0]
  const url = typeof input === 'string' ? input : input?.url || ''
  const isAuthEndpoint = /\/auth\/(login|register|token)/.test(url)

  if (response.status === 401 && !isAuthEndpoint && !handlingSessionExpired) {
    handlingSessionExpired = true

    // 清空登入態，避免回到頁面後仍持有過期 token
    localStorage.removeItem('auth-storage')

    await showSessionExpiredDialog('登入過期，請重新登錄')
    if (window.location.pathname !== '/login') {
      window.location.assign('/login')
    }

    setTimeout(() => {
      handlingSessionExpired = false
    }, 500)
  }

  return response
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
