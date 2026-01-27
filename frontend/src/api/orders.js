const API_BASE = '/api'

export async function createOrder(mapId, fromNode, toNode, orderInfo = {}) {
    const res = await fetch(`${API_BASE}/orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            map_id: mapId,
            from_node: fromNode,
            to_node: toNode,
            // 新增：訂單資訊用於訂單歷史
            store_name: orderInfo.storeName || null,
            items: orderInfo.items || null,
            total: orderInfo.total || null,
            user_email: orderInfo.userEmail || null
        })
    })
    if (!res.ok) {
        const error = await res.json().catch(() => ({}))
        throw new Error(error.detail || `HTTP ${res.status}`)
    }
    return res.json()
}

export async function getOrder(orderId) {
    const res = await fetch(`${API_BASE}/orders/${orderId}`)
    if (!res.ok) {
        const error = await res.json().catch(() => ({}))
        throw new Error(error.detail || `HTTP ${res.status}`)
    }
    return res.json()
}
