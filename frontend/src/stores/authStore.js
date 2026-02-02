import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const API_BASE = '/api'

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
                    return { success: true }
                } catch {
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

            // 新增訂單到歷史 (本地)
            addOrderToHistory: (order) => {
                const history = get().orderHistory
                set({ orderHistory: [order, ...history] })
            }
        }),
        {
            name: 'auth-storage',
        }
    )
)
