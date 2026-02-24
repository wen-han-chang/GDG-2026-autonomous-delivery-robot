import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createOrder, getOrder } from '../orders'

beforeEach(() => {
    vi.restoreAllMocks()
})

describe('createOrder', () => {
    it('returns order data on success', async () => {
        const orderData = { order_id: 'O1', path: ['A', 'B'] }
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            json: async () => orderData
        })
        const result = await createOrder('campus', 'A', 'B', { storeName: 'Store1', total: 200 }, 'test-token')
        expect(result).toEqual(orderData)
        expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8000/orders', expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({
                'Authorization': 'Bearer test-token'
            })
        }))
    })

    it('throws on HTTP error', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ detail: 'Invalid node' })
        })
        await expect(createOrder('campus', 'A', 'Z')).rejects.toThrow('Invalid node')
    })
})

describe('getOrder', () => {
    it('returns order data on success', async () => {
        const orderData = { order_id: 'O1', state: 'delivering' }
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: true,
            json: async () => orderData
        })
        const result = await getOrder('O1', 'test-token')
        expect(result).toEqual(orderData)
        expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8000/orders/O1', expect.objectContaining({
            headers: expect.objectContaining({
                'Authorization': 'Bearer test-token'
            })
        }))
    })

    it('throws on HTTP error', async () => {
        vi.spyOn(globalThis, 'fetch').mockResolvedValue({
            ok: false,
            status: 404,
            json: async () => ({ detail: 'Not found' })
        })
        await expect(getOrder('INVALID')).rejects.toThrow('Not found')
    })
})
