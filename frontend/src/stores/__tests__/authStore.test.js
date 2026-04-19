import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuthStore } from '../authStore'

const mockUser = { email: 'test@test.com', name: 'Test' }
const mockToken = 'jwt-token-123'

beforeEach(() => {
    useAuthStore.setState({ user: null, token: null, isLoggedIn: false, orderHistory: [] })
    vi.restoreAllMocks()
})

describe('login', () => {
    it('sets user and token on success', async () => {
        vi.spyOn(globalThis, 'fetch')
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ user: mockUser, token: mockToken })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => mockUser
            })
        const result = await useAuthStore.getState().login('test@test.com', 'pass')
        expect(result).toEqual({ success: true })
        expect(useAuthStore.getState().user).toEqual(mockUser)
        expect(useAuthStore.getState().token).toBe(mockToken)
        expect(useAuthStore.getState().isLoggedIn).toBe(true)
    })

    it('returns error on failure', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: false,
            json: async () => ({ detail: 'Invalid credentials' })
        })
        const result = await useAuthStore.getState().login('test@test.com', 'wrong')
        expect(result).toEqual({ success: false, error: 'Invalid credentials' })
        expect(useAuthStore.getState().isLoggedIn).toBe(false)
    })

    it('returns error on network failure', async () => {
        vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'))
        const result = await useAuthStore.getState().login('test@test.com', 'pass')
        expect(result.success).toBe(false)
    })
})

describe('register', () => {
    it('sets user and token on success', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            json: async () => ({ user: mockUser, token: mockToken })
        })
        const result = await useAuthStore.getState().register('test@test.com', 'pass', 'Test')
        expect(result).toEqual({ success: true })
        expect(useAuthStore.getState().isLoggedIn).toBe(true)
    })

    it('returns error on failure', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: false,
            json: async () => ({ detail: 'Email taken' })
        })
        const result = await useAuthStore.getState().register('test@test.com', 'pass', 'Test')
        expect(result).toEqual({ success: false, error: 'Email taken' })
    })
})

describe('logout', () => {
    it('clears state', () => {
        useAuthStore.setState({ user: mockUser, token: mockToken, isLoggedIn: true, orderHistory: [{ id: 'O1' }] })
        useAuthStore.getState().logout()
        expect(useAuthStore.getState().user).toBeNull()
        expect(useAuthStore.getState().token).toBeNull()
        expect(useAuthStore.getState().isLoggedIn).toBe(false)
        expect(useAuthStore.getState().orderHistory).toEqual([])
    })
})

describe('updateName', () => {
    it('updates user on success', async () => {
        useAuthStore.setState({ token: mockToken })
        const updatedUser = { ...mockUser, name: 'New Name' }
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            json: async () => ({ user: updatedUser })
        })
        const result = await useAuthStore.getState().updateName('New Name')
        expect(result).toEqual({ success: true })
        expect(useAuthStore.getState().user).toEqual(updatedUser)
    })

    it('returns error on failure', async () => {
        useAuthStore.setState({ token: mockToken })
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: false,
            json: async () => ({ detail: 'Update failed' })
        })
        const result = await useAuthStore.getState().updateName('New Name')
        expect(result).toEqual({ success: false, error: 'Update failed' })
    })
})

describe('updatePassword', () => {
    it('returns success on valid update', async () => {
        useAuthStore.setState({ token: mockToken })
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            json: async () => ({ message: 'ok' })
        })
        const result = await useAuthStore.getState().updatePassword('old', 'new')
        expect(result).toEqual({ success: true })
    })

    it('returns error on failure', async () => {
        useAuthStore.setState({ token: mockToken })
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: false,
            json: async () => ({ detail: 'Wrong password' })
        })
        const result = await useAuthStore.getState().updatePassword('wrong', 'new')
        expect(result).toEqual({ success: false, error: 'Wrong password' })
    })
})

describe('fetchOrderHistory', () => {
    it('sets orderHistory on success', async () => {
        useAuthStore.setState({ token: mockToken })
        const orders = [{ id: 'O1' }, { id: 'O2' }]
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            json: async () => orders
        })
        await useAuthStore.getState().fetchOrderHistory()
        expect(useAuthStore.getState().orderHistory).toEqual(orders)
    })
})
