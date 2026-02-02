import { describe, it, expect, beforeEach } from 'vitest'
import { useOrderStore } from '../orderStore'

beforeEach(() => {
    useOrderStore.setState({ currentOrder: null })
})

describe('setOrder', () => {
    it('sets the current order', () => {
        const order = { id: 'O1', state: 'pending' }
        useOrderStore.getState().setOrder(order)
        expect(useOrderStore.getState().currentOrder).toEqual(order)
    })
})

describe('clearOrder', () => {
    it('clears the current order', () => {
        useOrderStore.setState({ currentOrder: { id: 'O1' } })
        useOrderStore.getState().clearOrder()
        expect(useOrderStore.getState().currentOrder).toBeNull()
    })
})

describe('updateOrderState', () => {
    it('updates state when order exists', () => {
        useOrderStore.setState({ currentOrder: { id: 'O1', state: 'pending' } })
        useOrderStore.getState().updateOrderState('delivering')
        expect(useOrderStore.getState().currentOrder).toEqual({ id: 'O1', state: 'delivering' })
    })

    it('stays null when no order exists', () => {
        useOrderStore.getState().updateOrderState('delivering')
        expect(useOrderStore.getState().currentOrder).toBeNull()
    })
})
