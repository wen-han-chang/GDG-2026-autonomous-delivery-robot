import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// 從環境變數讀取後端網址，解決連線到前端 Nginx 的問題
const API_BASE = import.meta.env.VITE_API_URL

export const useAuthStore = create(
    persist(
        (set, get) => ({
            user: null,
            token: null,
            isLoggedIn: false,
            orderHistory: [],

            // 真正的登入 API
            login: async (email, password) => {
                try {
                    // 使用絕對路徑連往後端
                    const res = await fetch(`${API_BASE}/auth/login`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    })
                    const data = await res.json()

                    if (!res.ok) {
                        return { success: false, error: data.detail || '登入失敗' }
                    }

                    set({
                        user: data.user,
                        token: data.token,
                        isLoggedIn: true
                    })
                    // 登入後立即從後端同步最新資料（含頭像）
                    const meRes = await fetch(`${API_BASE}/users/me`, {
                        headers: { 'Authorization': `Bearer ${data.token}` }
                    })
                    if (meRes.ok) {
                        const me = await meRes.json()
                        set({ user: me })
                    }
                    return { success: true }
                } catch (err) {
                    console.error('Login error:', err)
                    return { success: false, error: '網路錯誤，請稍後再試' }
                }
            },

            // 真正的註冊 API
            register: async (email, password, name) => {
                try {
                    const res = await fetch(`${API_BASE}/auth/register`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password, name })
                    })
                    const data = await res.json()

                    if (!res.ok) {
                        return { success: false, error: data.detail || '註冊失敗' }
                    }

                    set({
                        user: data.user,
                        token: data.token,
                        isLoggedIn: true
                    })
                    return { success: true }
                } catch {
                    return { success: false, error: '網路錯誤，請稍後再試' }
                }
            },

            logout: () => {
                set({ user: null, token: null, isLoggedIn: false, orderHistory: [] })
            },

            // 更新使用者名稱
            updateName: async (newName) => {
                const token = get().token
                try {
                    const res = await fetch(`${API_BASE}/users/me`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({ name: newName })
                    })
                    const data = await res.json()

                    if (!res.ok) {
                        return { success: false, error: data.detail || '更新失敗' }
                    }

                    set({ user: data.user })
                    return { success: true }
                } catch {
                    return { success: false, error: '網路錯誤' }
                }
            },

            // 更新密碼
            updatePassword: async (oldPassword, newPassword) => {
                const token = get().token
                try {
                    const res = await fetch(`${API_BASE}/users/me`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
                    })
                    const data = await res.json()

                    if (!res.ok) {
                        return { success: false, error: data.detail || '更新失敗' }
                    }

                    return { success: true }
                } catch {
                    return { success: false, error: '網路錯誤' }
                }
            },

            // 從後端重新抓取最新使用者資料
            fetchMe: async () => {
                const token = get().token
                if (!token) return
                try {
                    const res = await fetch(`${API_BASE}/users/me`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    })
                    if (res.ok) {
                        const user = await res.json()
                        set({ user })
                    }
                } catch {
                    console.error('Failed to fetch user data')
                }
            },

            // 取得訂單歷史
            fetchOrderHistory: async () => {
                const token = get().token
                if (!token) return

                try {
                    const res = await fetch(`${API_BASE}/users/me/orders`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    })
                    if (res.ok) {
                        const orders = await res.json()
                        set({ orderHistory: orders })
                    }
                } catch {
                    console.error('Failed to fetch order history')
                }
            },

            // 更新頭像
            updateAvatar: async (avatarDataUrl) => {
                const token = get().token
                try {
                    const res = await fetch(`${API_BASE}/users/me/avatar`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({ avatar: avatarDataUrl })
                    })
                    const data = await res.json()
                    if (!res.ok) {
                        return { success: false, error: data.detail || '更新失敗' }
                    }
                    set({ user: { ...get().user, avatar: data.avatar } })
                    return { success: true }
                } catch {
                    return { success: false, error: '網路錯誤' }
                }
            },

            // 新增訂單到歷史 (本地)
            addOrderToHistory: (order) => {
                const history = get().orderHistory
                set({ orderHistory: [order, ...history] })
            }
        }),
        {
            name: 'auth-storage', // 這裡會把資料存在 localStorage
        }
    )
)
