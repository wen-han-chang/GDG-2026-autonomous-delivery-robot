import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
    persist(
        (set, get) => ({
            user: null,
            token: null,
            isLoggedIn: false,
            orderHistory: [], // Mock 訂單歷史

            // Mock login - 之後串接後端時改這裡
            login: async (email, password) => {
                // TODO: 呼叫 POST /auth/login
                // 目前用 mock
                if (email && password) {
                    const mockUser = {
                        id: 'U001',
                        email: email,
                        name: email.split('@')[0],
                        createdAt: new Date().toISOString(),
                    }
                    const mockToken = 'mock-token-' + Date.now()
                    set({ user: mockUser, token: mockToken, isLoggedIn: true })
                    return { success: true }
                }
                return { success: false, error: '請輸入帳號密碼' }
            },

            // Mock register
            register: async (email, password, name) => {
                // TODO: 呼叫 POST /auth/register
                if (email && password && name) {
                    const mockUser = {
                        id: 'U' + Date.now(),
                        email: email,
                        name: name,
                        createdAt: new Date().toISOString(),
                    }
                    const mockToken = 'mock-token-' + Date.now()
                    // Mock 訂單歷史
                    const mockOrderHistory = [
                        {
                            id: 'O001',
                            date: '2026-01-18',
                            store: '讚野烤肉飯',
                            items: ['招牌便當 x1', '紅茶 x2'],
                            total: 130,
                            status: '已完成'
                        },
                        {
                            id: 'O002',
                            date: '2026-01-19',
                            store: '台灣第二味',
                            items: ['珍珠奶茶 x3'],
                            total: 105,
                            status: '已完成'
                        }
                    ]
                    set({
                        user: mockUser,
                        token: mockToken,
                        isLoggedIn: true,
                        orderHistory: mockOrderHistory
                    })
                    return { success: true }
                }
                return { success: false, error: '請填寫所有欄位' }
            },

            logout: () => {
                set({ user: null, token: null, isLoggedIn: false, orderHistory: [] })
            },

            // 更新使用者名稱
            updateName: (newName) => {
                const user = get().user
                if (user) {
                    set({ user: { ...user, name: newName } })
                    return { success: true }
                }
                return { success: false, error: '未登入' }
            },

            // 更新密碼 (mock)
            updatePassword: (oldPassword, newPassword) => {
                // TODO: 呼叫後端 API 驗證舊密碼
                // 目前 mock 直接成功
                if (oldPassword && newPassword) {
                    return { success: true }
                }
                return { success: false, error: '請填寫密碼' }
            },

            // 新增訂單到歷史
            addOrderToHistory: (order) => {
                const history = get().orderHistory
                set({ orderHistory: [order, ...history] })
            }
        }),
        {
            name: 'auth-storage', // localStorage key
        }
    )
)
