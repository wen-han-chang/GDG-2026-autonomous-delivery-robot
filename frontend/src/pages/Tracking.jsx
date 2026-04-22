import { useState, useEffect, useMemo, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useOrderStore } from '../stores/orderStore'
import { useAuthStore } from '../stores/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { getOrder } from '../api/orders'
import LiveMap from '../components/LiveMap'

const API_BASE = import.meta.env.VITE_API_URL
const DEFAULT_AVG_SPEED_CM_S = 12.0
const ROUTE_BREAK = '__ROUTE_BREAK__'

function buildAdj(mapData) {
    const nodesById = new Map((mapData.nodes || []).map(n => [n.id, n]))
    const adj = new Map((mapData.nodes || []).map(n => [n.id, []]))

    for (const edge of mapData.edges || []) {
        const from = edge.from
        const to = edge.to
        if (!adj.has(from) || !adj.has(to)) continue

        const fromNode = nodesById.get(from)
        const toNode = nodesById.get(to)
        if (!fromNode || !toNode) continue

        const length = edge.length ?? Math.hypot(fromNode.x - toNode.x, fromNode.y - toNode.y)
        adj.get(from).push({ to, w: length })
        if (edge.bidirectional !== false) {
            adj.get(to).push({ to: from, w: length })
        }
    }

    return adj
}

function shortestDistance(mapData, start, goal) {
    if (!start || !goal || start === goal) return 0
    const adj = buildAdj(mapData)
    if (!adj.has(start) || !adj.has(goal)) return Infinity

    const dist = new Map()
    for (const k of adj.keys()) dist.set(k, Infinity)
    dist.set(start, 0)

    const visited = new Set()
    while (true) {
        let u = null
        let best = Infinity
        for (const [k, d] of dist.entries()) {
            if (!visited.has(k) && d < best) {
                best = d
                u = k
            }
        }

        if (u === null) break
        if (u === goal) return dist.get(u)
        visited.add(u)

        for (const e of adj.get(u)) {
            const cand = dist.get(u) + e.w
            if (cand < dist.get(e.to)) {
                dist.set(e.to, cand)
            }
        }
    }

    return Infinity
}

function shortestPath(mapData, start, goal) {
    if (!start || !goal) return []
    if (start === goal) return [start]

    const adj = buildAdj(mapData)
    if (!adj.has(start) || !adj.has(goal)) return []

    const dist = new Map()
    const prev = new Map()
    for (const k of adj.keys()) dist.set(k, Infinity)
    dist.set(start, 0)

    const visited = new Set()
    while (true) {
        let u = null
        let best = Infinity
        for (const [k, d] of dist.entries()) {
            if (!visited.has(k) && d < best) {
                best = d
                u = k
            }
        }

        if (u === null) break
        if (u === goal) break
        visited.add(u)

        for (const e of adj.get(u)) {
            const cand = dist.get(u) + e.w
            if (cand < dist.get(e.to)) {
                dist.set(e.to, cand)
                prev.set(e.to, u)
            }
        }
    }

    if (!Number.isFinite(dist.get(goal))) return []

    const path = []
    let cur = goal
    while (cur != null) {
        path.push(cur)
        cur = prev.get(cur)
    }
    path.reverse()
    return path
}

function compressConsecutive(nodes) {
    if (!Array.isArray(nodes) || nodes.length === 0) return []
    const out = [nodes[0]]
    for (let i = 1; i < nodes.length; i++) {
        if (nodes[i] !== nodes[i - 1]) out.push(nodes[i])
    }
    return out
}

function expandWaypointRoute(mapData, waypoints) {
    if (!mapData || !Array.isArray(waypoints) || waypoints.length === 0) return []
    if (waypoints.length === 1) return [waypoints[0]]

    const expanded = [waypoints[0]]
    for (let i = 0; i < waypoints.length - 1; i++) {
        const from = waypoints[i]
        const to = waypoints[i + 1]
        if (from === to) continue

        const seg = shortestPath(mapData, from, to)
        if (seg.length > 1) {
            expanded.push(...seg.slice(1))
        } else {
            expanded.push(to)
        }
    }
    return compressConsecutive(expanded)
}

function mergeOrderData(apiOrder, cachedOrder, currentOrderId) {
    if (!apiOrder) return cachedOrder
    if (!cachedOrder || cachedOrder.order_id !== currentOrderId) return apiOrder

    return {
        ...apiOrder,
        is_multi_store: cachedOrder.is_multi_store || false,
        batch_order_ids: cachedOrder.batch_order_ids || [],
        batch_orders: cachedOrder.batch_orders || [],
        assigned_robot_id: apiOrder.assigned_robot_id || cachedOrder.assigned_robot_id || null,
    }
}

function readBatchMeta(orderId) {
    if (!orderId) return null
    try {
        const raw = sessionStorage.getItem(`tracking_batch_${orderId}`)
        if (!raw) return null
        const parsed = JSON.parse(raw)
        if (!parsed || !Array.isArray(parsed.batch_order_ids)) return null
        return {
            is_multi_store: !!parsed.is_multi_store,
            batch_order_ids: parsed.batch_order_ids,
            batch_orders: Array.isArray(parsed.batch_orders) ? parsed.batch_orders : [],
        }
    } catch {
        return null
    }
}

export default function Tracking() {
    const { orderId } = useParams()
    const [mapData, setMapData] = useState(null)
    const [order, setOrder] = useState(null)
    const [plannerStatus, setPlannerStatus] = useState(null)
    const [batchProgress, setBatchProgress] = useState(null)
    const [orderNotFound, setOrderNotFound] = useState(false)
    const completionLockedOrderIdsRef = useRef(new Set())

    const storedOrder = useOrderStore((state) => state.currentOrder)
    const websocketRobotId = order?.assigned_robot_id || storedOrder?.assigned_robot_id || null
    const { robotState, connected, error } = useWebSocket(orderId, websocketRobotId)
    const batchMeta = useMemo(() => readBatchMeta(orderId), [orderId])

    // Load order data（首次 + 輪詢，確保自動清單後狀態會更新）
    useEffect(() => {
        const token = useAuthStore.getState().token

        let cancelled = false

        const fetchOrder = async () => {
            try {
                const data = await getOrder(orderId, token)
                if (cancelled) return
                setOrderNotFound(false)
                setOrder((prev) => {
                    const merged = mergeOrderData(data, prev || storedOrder, orderId)
                    if (!batchMeta) return merged
                    return {
                        ...merged,
                        ...batchMeta,
                    }
                })
            } catch (err) {
                const msg = String(err?.message || '')
                const notFound = msg.includes('Order not found')
                if (notFound) {
                    setOrderNotFound(true)
                }
                console.error('Failed to load order:', err)
            }
        }

        fetchOrder()
        const timer = setInterval(fetchOrder, 3000)

        return () => {
            cancelled = true
            clearInterval(timer)
        }
    }, [orderId, storedOrder, batchMeta])

    // 使用 storedOrder 作為預設值
    const activeOrder = useMemo(() => {
        const base = order || (storedOrder?.order_id === orderId ? storedOrder : null)
        if (!base) return null
        if (!batchMeta) return base
        return {
            ...base,
            ...batchMeta,
        }
    }, [order, storedOrder, orderId, batchMeta])

    // Load map data（九宮格節點與邊）
    useEffect(() => {
        fetch('/map.json')
            .then(res => res.json())
            .then(data => {
                setMapData({ nodes: data.nodes, edges: data.edges })
            })
    }, [])

    // 讀取 planner/status，顯示整台車完整多店規劃
    useEffect(() => {
        const robotId = order?.assigned_robot_id
        if (!robotId) return

        let cancelled = false

        const fetchStatus = async () => {
            try {
                const res = await fetch(`${API_BASE}/planner/status?robot_id=${encodeURIComponent(robotId)}`)
                if (!res.ok) return
                const data = await res.json()
                if (!cancelled) {
                    setPlannerStatus(data)
                }
            } catch {
                // Ignore intermittent polling errors.
            }
        }

        fetchStatus()
        const timer = setInterval(fetchStatus, 2000)

        return () => {
            cancelled = true
            clearInterval(timer)
        }
    }, [order?.assigned_robot_id])

    const batchOrderRoutes = useMemo(() => {
        if (!activeOrder?.is_multi_store || !Array.isArray(activeOrder.batch_orders)) return []
        return activeOrder.batch_orders
            .map((o) => ({
                orderId: o.order_id,
                route: Array.isArray(o.route) ? o.route : [],
            }))
            .filter((o) => o.route.length > 1)
    }, [activeOrder])

    // 多店模式：輪詢整批子單狀態，避免「第一筆 DELIVERED 就提早顯示完成」
    useEffect(() => {
        const ids = activeOrder?.batch_order_ids
        const isMulti = !!activeOrder?.is_multi_store
        if (!isMulti || !Array.isArray(ids) || ids.length === 0) {
            return
        }

        let cancelled = false
        const token = useAuthStore.getState().token

        const fetchBatch = async () => {
            try {
                const settled = await Promise.allSettled(ids.map((id) => getOrder(id, token)))
                if (cancelled) return

                const details = []
                let notFoundCount = 0
                settled.forEach((item) => {
                    if (item.status === 'fulfilled') {
                        details.push(item.value)
                    } else {
                        const msg = String(item.reason?.message || '')
                        if (msg.includes('Order not found')) {
                            notFoundCount += 1
                        }
                    }
                })

                const deliveredCount = details.filter((o) => o.status === 'DELIVERED').length
                const pickedCount = details.filter((o) => o.status === 'PICKED').length
                const assignedCount = details.filter((o) => o.status === 'ASSIGNED').length
                const pendingNow = (plannerStatus?.pending_count ?? 0) > 0
                const allGoneAfterCleanup = details.length === 0 && notFoundCount === ids.length && !pendingNow

                setBatchProgress({
                    total: ids.length,
                    deliveredCount,
                    pickedCount,
                    assignedCount,
                    allDelivered: allGoneAfterCleanup || ((deliveredCount + notFoundCount) === ids.length),
                    details,
                })
            } catch {
                if (!cancelled) {
                    setBatchProgress((prev) => prev ? {
                        ...prev,
                        allDelivered: false,
                        details: prev.details || [],
                    } : null)
                }
            }
        }

        fetchBatch()
        const timer = setInterval(fetchBatch, 3000)
        return () => {
            cancelled = true
            clearInterval(timer)
        }
    }, [activeOrder?.is_multi_store, activeOrder?.batch_order_ids, orderId, plannerStatus?.pending_count])

    const orderRoute = useMemo(() => {
        if (batchOrderRoutes.length === 0) {
            return activeOrder?.route || []
        }

        const merged = []
        batchOrderRoutes.forEach((o, idx) => {
            if (idx > 0) {
                merged.push(ROUTE_BREAK)
            }
            merged.push(...o.route)
        })
        return merged
    }, [activeOrder, batchOrderRoutes])

    const robotGlobalWaypoints = useMemo(() => {
        const stops = plannerStatus?.plan_stops || []
        if (!stops.length) return []
        const startNode = plannerStatus?.current_node || 'A'
        return [startNode, ...stops]
    }, [plannerStatus])

    const robotGlobalRoute = useMemo(() => {
        return compressConsecutive(robotGlobalWaypoints)
    }, [robotGlobalWaypoints])

    const hasPendingGlobal = (plannerStatus?.pending_count ?? 0) > 0
    const isMultiStore = !!activeOrder?.is_multi_store
    const cleanupCompleted = orderNotFound
    const ownOrderCompleted = isMultiStore
        ? !!batchProgress?.allDelivered || cleanupCompleted
        : activeOrder?.status === 'DELIVERED' || cleanupCompleted
    if (ownOrderCompleted) {
        completionLockedOrderIdsRef.current.add(orderId)
    }
    const isCompleted = completionLockedOrderIdsRef.current.has(orderId) || ownOrderCompleted

    const orderRouteForMap = useMemo(() => {
        if (!orderRoute?.length) return []

        const startNode = plannerStatus?.current_node
        if (!startNode) return orderRoute
        if (orderRoute[0] === startNode) return orderRoute

        return [startNode, ...orderRoute]
    }, [orderRoute, plannerStatus])

    const orderWaypoints = useMemo(() => {
        return (orderRouteForMap || []).filter((n) => n !== ROUTE_BREAK)
    }, [orderRouteForMap])

    const globalExpandedRoute = useMemo(() => {
        return expandWaypointRoute(mapData, robotGlobalRoute)
    }, [mapData, robotGlobalRoute])

    const orderExpandedRoute = useMemo(() => {
        return expandWaypointRoute(mapData, orderWaypoints)
    }, [mapData, orderWaypoints])

    const ownTerminalNode = useMemo(() => {
        if (batchOrderRoutes.length > 0) {
            const lastRoute = batchOrderRoutes[batchOrderRoutes.length - 1]?.route || []
            if (lastRoute.length > 0) return lastRoute[lastRoute.length - 1]
        }
        if (orderExpandedRoute.length > 0) {
            return orderExpandedRoute[orderExpandedRoute.length - 1]
        }
        if (orderWaypoints.length > 0) {
            return orderWaypoints[orderWaypoints.length - 1]
        }
        const rawRoute = activeOrder?.route || []
        if (rawRoute.length > 0) {
            return rawRoute[rawRoute.length - 1]
        }
        return null
    }, [batchOrderRoutes, orderExpandedRoute, orderWaypoints, activeOrder])

    const completedDisplayNode = useMemo(() => {
        return robotState?.node
            || plannerStatus?.current_node
            || orderExpandedRoute[orderExpandedRoute.length - 1]
            || orderWaypoints[orderWaypoints.length - 1]
            || null
    }, [robotState, plannerStatus, orderExpandedRoute, orderWaypoints])

    const mapRoute = useMemo(() => {
        if (isCompleted) {
            const fixedNode = ownTerminalNode || completedDisplayNode
            return fixedNode ? [fixedNode] : []
        }
        if (hasPendingGlobal && globalExpandedRoute.length > 1) return globalExpandedRoute
        return orderExpandedRoute
    }, [isCompleted, ownTerminalNode, completedDisplayNode, hasPendingGlobal, globalExpandedRoute, orderExpandedRoute])

    const personalEtaRoute = useMemo(() => {
        if (isCompleted) return []

        const currentNode = robotState?.node || plannerStatus?.current_node || null
        if (!currentNode || !mapData) return []

        const planStops = plannerStatus?.plan_stops || []
        if (planStops.length === 0) return []

        // 建立本訂單待拜訪節點的 multiset（計數 Map）。
        // 直接信任後端 plan_stops 的拜訪順序，不做任何貪婪重排——
        // 貪婪排序容易與後端最優路徑衝突，導致對齊失敗後退回錯誤路徑。
        const nodeCounts = new Map()

        if (isMultiStore && Array.isArray(batchProgress?.details)) {
            batchProgress.details.forEach((o) => {
                if (o.status === 'DELIVERED') return
                const route = Array.isArray(o.route) ? o.route : []
                if (route.length === 0) return

                const pickup = route[0]
                const drop = route[route.length - 1]
                if (o.status !== 'PICKED' && pickup) {
                    nodeCounts.set(pickup, (nodeCounts.get(pickup) || 0) + 1)
                }
                if (drop) {
                    nodeCounts.set(drop, (nodeCounts.get(drop) || 0) + 1)
                }
            })
        } else {
            const route = Array.isArray(activeOrder?.route) ? activeOrder.route : []
            if (activeOrder?.status !== 'DELIVERED' && route.length > 0) {
                const pickup = route[0]
                const drop = route[route.length - 1]
                if (activeOrder?.status !== 'PICKED' && pickup) {
                    nodeCounts.set(pickup, (nodeCounts.get(pickup) || 0) + 1)
                }
                if (drop) {
                    nodeCounts.set(drop, (nodeCounts.get(drop) || 0) + 1)
                }
            }
        }

        if (nodeCounts.size === 0) return []

        // 依 plan_stops 原序收集屬於本訂單的節點（multiset 消耗法），
        // 自動過濾其他併單訂單的停靠點，並完整保留重複節點（如多次抵達同一送貨點）。
        const counts = new Map(nodeCounts)
        const collected = [currentNode]
        for (const node of planStops) {
            const cnt = counts.get(node) || 0
            if (cnt > 0) {
                collected.push(node)
                if (cnt === 1) counts.delete(node)
                else counts.set(node, cnt - 1)
            }
            if (counts.size === 0) break
        }

        return expandWaypointRoute(mapData, collected)
    }, [isCompleted, robotState, plannerStatus, isMultiStore, batchProgress, activeOrder, mapData])

    const segmentEtas = useMemo(() => {
        if (!mapData) return []

        const rows = []
        if (!personalEtaRoute || personalEtaRoute.length < 2) return []
        for (let i = 0; i < personalEtaRoute.length - 1; i++) {
            const from = personalEtaRoute[i]
            const to = personalEtaRoute[i + 1]

            const d = shortestDistance(mapData, from, to)
            rows.push({
                from,
                to,
                distanceCm: Number.isFinite(d) ? Math.round(d) : null,
                etaSec: Number.isFinite(d) ? d / DEFAULT_AVG_SPEED_CM_S : null,
            })
        }
        return rows
    }, [mapData, personalEtaRoute])

    const personalPlanActions = useMemo(() => {
        if (isCompleted) return []

        if (isMultiStore && Array.isArray(batchProgress?.details)) {
            const rows = []
            const idToSeq = new Map((activeOrder?.batch_order_ids || []).map((id, i) => [id, i + 1]))
            batchProgress.details.forEach((o, idx) => {
                const route = Array.isArray(o.route) ? o.route : []
                if (!route.length || o.status === 'DELIVERED') return

                const detailId = o.order_id || o.id || null
                const seq = detailId ? (idToSeq.get(detailId) || (idx + 1)) : (idx + 1)
                const pickup = route[0]
                const drop = route[route.length - 1]
                if (o.status !== 'PICKED' && pickup) {
                    rows.push(`子單${seq}(${detailId || 'unknown'}) 取餐：${pickup}`)
                }
                if (drop) {
                    rows.push(`子單${seq}(${detailId || 'unknown'}) 送達：${drop}`)
                }
            })
            return rows
        }

        if (!orderExpandedRoute.length) return []

        const pickup = orderExpandedRoute[0]
        const drop = orderExpandedRoute[orderExpandedRoute.length - 1]
        const rows = []
        if (pickup) rows.push(`取餐：${pickup}`)
        if (drop && drop !== pickup) rows.push(`送達：${drop}`)
        return rows
    }, [isCompleted, isMultiStore, batchProgress, activeOrder, orderExpandedRoute])

    const totalPlannedEtaSec = useMemo(() => {
        if (isCompleted) return 0
        return segmentEtas.reduce((acc, s) => acc + (s.etaSec || 0), 0)
    }, [segmentEtas, isCompleted])

    // 計算機器人位置（使用 useMemo 避免 effect 內 setState）
    const robotPosition = useMemo(() => {
        if (!robotState) return null
        return { node: robotState.node }

        // NOTE: 保留原邏輯供未來插值動畫使用
        // if (!robotState || !mapData || !plannedRoute) return null
        // const { node, progress } = robotState
        // const route = plannedRoute
        // ...

        // return currentNode ? { x: currentNode.x, y: currentNode.y } : null
    }, [robotState])

    const derivedState = useMemo(() => {
        if (isCompleted) return 'ARRIVED'

        if (isMultiStore && batchProgress) {
            if (batchProgress.pickedCount > 0 || batchProgress.deliveredCount > 0) return 'MOVING'
            if (batchProgress.assignedCount > 0) return 'ASSIGNED'
        }

        if (robotState?.state) return robotState.state

        switch (activeOrder?.status) {
            case 'DELIVERED':
                return 'ARRIVED'
            case 'PICKED':
                return 'MOVING'
            case 'ASSIGNED':
                return 'ASSIGNED'
            case 'CREATED':
                return 'IDLE'
            default:
                return null
        }
    }, [isCompleted, isMultiStore, batchProgress, robotState, activeOrder])

    const getStatusText = () => {
        if (!derivedState) return '等待配送...'
        switch (derivedState) {
            case 'IDLE': return '準備中'
            case 'ASSIGNED': return '已派單'
            case 'MOVING': return '配送中'
            case 'ARRIVED': return '已送達'
            default: return derivedState
        }
    }

    const getStatusColor = () => {
        if (!derivedState) return 'bg-gray-500'
        switch (derivedState) {
            case 'ARRIVED': return 'bg-green-500'
            case 'MOVING': return 'bg-orange-500'
            default: return 'bg-blue-500'
        }
    }

    return (
        <div className="max-w-2xl mx-auto px-4 py-8">
            <div className="mb-6">
                <Link to="/" className="text-orange-600 hover:text-orange-700">
                    ← 返回首頁
                </Link>
            </div>

            <div className="bg-white rounded-xl shadow-md overflow-hidden">
                <div className="p-6 border-b border-gray-100">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-xl font-bold text-gray-800">
                                訂單 #{orderId}
                            </h1>
                            <div className="flex items-center gap-2 mt-2">
                                <span className={`${getStatusColor()} text-white px-3 py-1 rounded-full text-sm font-medium`}>
                                    {getStatusText()}
                                </span>
                                {connected && (
                                    <span className="text-green-500 text-sm flex items-center gap-1">
                                        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                                        即時連線中
                                    </span>
                                )}
                                {!connected && !error && (
                                    <span className="text-yellow-500 text-sm flex items-center gap-1">
                                        <span className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></span>
                                        連線中...
                                    </span>
                                )}
                                {error && derivedState !== 'ARRIVED' && (
                                    <span className={`${error.includes('重試中') ? 'text-yellow-600' : 'text-red-500'} text-sm flex items-center gap-1`}>
                                        <span className={`w-2 h-2 rounded-full ${error.includes('重試中') ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`}></span>
                                        {error}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="p-6">
                    {mapData && (
                        <LiveMap
                            mapData={mapData}
                            robotPosition={robotPosition}
                            route={mapRoute}
                        />
                    )}

                    {robotState && (
                        <div className="mt-4 grid grid-cols-3 gap-4 text-center">
                            <div className="bg-gray-50 rounded-lg p-3">
                                <div className="text-sm text-gray-500">目前位置</div>
                                <div className="font-bold text-gray-800">{robotState.node}</div>
                            </div>
                            <div className="bg-gray-50 rounded-lg p-3">
                                <div className="text-sm text-gray-500">進度</div>
                                <div className="font-bold text-gray-800">{Math.round(robotState.progress * 100)}%</div>
                            </div>
                            <div className="bg-gray-50 rounded-lg p-3">
                                <div className="text-sm text-gray-500">速度</div>
                                <div className="font-bold text-gray-800">{robotState.speed} cm/s</div>
                            </div>
                        </div>
                    )}

                    {(activeOrder || plannerStatus) && (
                        <div className="mt-6 p-4 bg-orange-50 rounded-lg">
                            <div className="text-sm text-gray-600">
                                <strong>本訂單站點：</strong>{' '}
                                {batchOrderRoutes.length > 0
                                    ? batchOrderRoutes.map((item, idx) => `子單${idx + 1}(${item.orderId})：${item.route.join(' → ')}`).join(' | ')
                                    : orderRoute?.join(' → ')}
                            </div>
                            {!isCompleted && hasPendingGlobal && robotGlobalRoute.length > 0 && (
                                <div className="text-sm text-gray-500 mt-1">
                                    <strong>小車目前全域規劃（停靠點）：</strong> {robotGlobalRoute.join(' → ')}
                                </div>
                            )}
                            {!isCompleted && hasPendingGlobal && mapRoute.length > 1 && (
                                <div className="text-sm text-gray-500 mt-1">
                                    <strong>小車目前全域路徑：</strong> {mapRoute.join(' → ')}
                                </div>
                            )}
                            <div className="text-sm text-gray-600 mt-1">
                                <strong>整體預估時間：</strong> {totalPlannedEtaSec.toFixed(1)} 秒
                            </div>
                            {personalPlanActions.length > 0 && (
                                <div className="mt-3">
                                    <div className="font-semibold text-gray-700 mb-2">本訂單規劃動作</div>
                                    <ul className="space-y-1 text-sm text-gray-600">
                                        {personalPlanActions.map((a, idx) => (
                                            <li key={`${a}-${idx}`}>{idx + 1}. {a}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {segmentEtas.length > 0 && (
                                <div className="mt-3">
                                    <div className="font-semibold text-gray-700 mb-2">分段預估</div>
                                    <ul className="space-y-1 text-sm text-gray-600">
                                        {segmentEtas.map((s, idx) => (
                                            <li key={`${s.from}-${s.to}-${idx}`}>
                                                {s.from} → {s.to}：
                                                {s.etaSec === null ? ' 無法計算' : ` 約 ${s.etaSec.toFixed(1)} 秒 (${s.distanceCm} cm)`}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {batchOrderRoutes.length > 1 && (
                                <div className="text-xs text-gray-500 mt-2">
                                    子單為「每間店一筆」建立；分段預估以小車全域執行順序為準。
                                </div>
                            )}
                            <div className="text-xs text-gray-500 mt-3">
                                ETA 計算使用預設速度 {DEFAULT_AVG_SPEED_CM_S} cm/s
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {derivedState === 'ARRIVED' && (
                <div className="mt-6 bg-green-50 border border-green-200 rounded-xl p-6 text-center">
                    <div className="text-4xl mb-2">🎉</div>
                    <h2 className="text-xl font-bold text-green-700">配送完成！</h2>
                    <p className="text-green-600 mt-1">您的餐點已送達</p>
                </div>
            )}
        </div>
    )
}
