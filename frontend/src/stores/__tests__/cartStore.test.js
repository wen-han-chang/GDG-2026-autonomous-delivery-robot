import { describe, it, expect, beforeEach } from 'vitest'
import { useCartStore } from '../cartStore'

const product1 = { id: 'p1', name: 'Burger', price: 100 }
const product2 = { id: 'p2', name: 'Fries', price: 50 }

beforeEach(() => {
    useCartStore.setState({ items: [] })
})

describe('addItem', () => {
    it('adds a new item with quantity 1', () => {
        useCartStore.getState().addItem(product1)
        const items = useCartStore.getState().items
        expect(items).toHaveLength(1)
        expect(items[0]).toEqual({ ...product1, quantity: 1 })
    })

    it('increments quantity for duplicate item', () => {
        useCartStore.getState().addItem(product1)
        useCartStore.getState().addItem(product1)
        const items = useCartStore.getState().items
        expect(items).toHaveLength(1)
        expect(items[0].quantity).toBe(2)
    })
})

describe('removeItem', () => {
    it('removes item by id', () => {
        useCartStore.setState({ items: [{ ...product1, quantity: 1 }, { ...product2, quantity: 1 }] })
        useCartStore.getState().removeItem('p1')
        const items = useCartStore.getState().items
        expect(items).toHaveLength(1)
        expect(items[0].id).toBe('p2')
    })
})

describe('updateQuantity', () => {
    it('updates quantity for an item', () => {
        useCartStore.setState({ items: [{ ...product1, quantity: 1 }] })
        useCartStore.getState().updateQuantity('p1', 5)
        expect(useCartStore.getState().items[0].quantity).toBe(5)
    })

    it('removes item when quantity <= 0', () => {
        useCartStore.setState({ items: [{ ...product1, quantity: 1 }] })
        useCartStore.getState().updateQuantity('p1', 0)
        expect(useCartStore.getState().items).toHaveLength(0)
    })
})

describe('clearCart', () => {
    it('clears all items', () => {
        useCartStore.setState({ items: [{ ...product1, quantity: 2 }] })
        useCartStore.getState().clearCart()
        expect(useCartStore.getState().items).toHaveLength(0)
    })
})

describe('getTotal', () => {
    it('returns sum of price * quantity', () => {
        useCartStore.setState({
            items: [
                { ...product1, quantity: 2 },
                { ...product2, quantity: 3 }
            ]
        })
        expect(useCartStore.getState().getTotal()).toBe(2 * 100 + 3 * 50)
    })
})

describe('getItemCount', () => {
    it('returns total quantity of all items', () => {
        useCartStore.setState({
            items: [
                { ...product1, quantity: 2 },
                { ...product2, quantity: 3 }
            ]
        })
        expect(useCartStore.getState().getItemCount()).toBe(5)
    })
})
