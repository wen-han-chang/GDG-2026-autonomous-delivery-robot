const API_BASE = import.meta.env.VITE_API_URL

export async function createOrder(mapId, storeId, toNode, orderInfo = {}, token) {
    const headers = { 'Content-Type': 'application/json' }
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const res = await fetch(`${API_BASE}/orders`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            map_id: mapId,
            store_id: storeId,
            to_node: toNode,
            store_name: orderInfo.storeName || null,
            items: orderInfo.items || null,
            total: orderInfo.total || null,
        })
    })
    if (!res.ok) {
        const error = await res.json().catch(() => ({}))
        throw new Error(error.detail || `HTTP ${res.status}`)
    }
    return res.json()
}

export async function createMultiStoreOrder(mapId, storeIds, toNode, orderInfo = {}, token) {
    const headers = { 'Content-Type': 'application/json' }
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const res = await fetch(`${API_BASE}/orders/multi`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            map_id: mapId,
            store_ids: storeIds,
            to_node: toNode,
            items: orderInfo.items || null,
            items_by_store: orderInfo.itemsByStore || null,
            total: orderInfo.total || null,
        })
    })
    if (!res.ok) {
        const error = await res.json().catch(() => ({}))
        throw new Error(error.detail || `HTTP ${res.status}`)
    }
    return res.json()
}

export async function getOrder(orderId, token) {
    const headers = {}
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const res = await fetch(`${API_BASE}/orders/${orderId}`, { headers })
    if (!res.ok) {
        const error = await res.json().catch(() => ({}))
        throw new Error(error.detail || `HTTP ${res.status}`)
    }
    return res.json()
}
