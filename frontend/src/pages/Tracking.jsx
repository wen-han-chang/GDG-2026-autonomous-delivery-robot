import { useState, useEffect, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useOrderStore } from '../stores/orderStore'
import { useAuthStore } from '../stores/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { getOrder } from '../api/orders'
import LiveMap from '../components/LiveMap'

export default function Tracking() {
    const { orderId } = useParams()
    const [mapData, setMapData] = useState(null)
    const [order, setOrder] = useState(null)

    const { robotState, connected, error } = useWebSocket(orderId)
    const storedOrder = useOrderStore((state) => state.currentOrder)

    // Load order data
    useEffect(() => {
        if (storedOrder && storedOrder.order_id === orderId) {
            return
        }
        const token = useAuthStore.getState().token
        getOrder(orderId, token)
            .then(data => setOrder(data))
            .catch(_err => console.error('Failed to load order:', _err))
    }, [orderId, storedOrder])

    // 使用 storedOrder 作為預設值
    const activeOrder = order || (storedOrder?.order_id === orderId ? storedOrder : null)

    // Load map data（九宮格節點與邊）
    useEffect(() => {
        fetch('/map.json')
            .then(res => res.json())
            .then(data => {
                setMapData({ nodes: data.nodes, edges: data.edges })
            })
    }, [])

    // 計算機器人位置（使用 useMemo 避免 effect 內 setState）
    const robotPosition = useMemo(() => {
        if (!robotState || !mapData || !activeOrder?.route) return null

        const { node, progress } = robotState
        const route = activeOrder.route
        const nodeIndex = route.indexOf(node)

        if (nodeIndex === -1) {
            const found = mapData.nodes.find(n => n.id === node)
            return found ? { x: found.x, y: found.y } : null
        }

        const currentNode = mapData.nodes.find(n => n.id === route[nodeIndex])
        const nextNode = nodeIndex < route.length - 1
            ? mapData.nodes.find(n => n.id === route[nodeIndex + 1])
            : null

        if (currentNode && nextNode) {
            return {
                x: currentNode.x + (nextNode.x - currentNode.x) * progress,
                y: currentNode.y + (nextNode.y - currentNode.y) * progress
            }
        }
        return currentNode ? { x: currentNode.x, y: currentNode.y } : null
    }, [robotState, mapData, activeOrder])

    const getStatusText = () => {
        if (!robotState) return '等待配送...'
        switch (robotState.state) {
            case 'IDLE': return '準備中'
            case 'ASSIGNED': return '已派單'
            case 'MOVING': return '配送中'
            case 'ARRIVED': return '已送達'
            default: return robotState.state
        }
    }

    const getStatusColor = () => {
        if (!robotState) return 'bg-gray-500'
        switch (robotState.state) {
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
                                {error && (
                                    <span className="text-red-500 text-sm flex items-center gap-1">
                                        <span className="w-2 h-2 bg-red-500 rounded-full"></span>
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
                            route={activeOrder?.route}
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

                    {activeOrder && (
                        <div className="mt-6 p-4 bg-orange-50 rounded-lg">
                            <div className="text-sm text-gray-600">
                                <strong>路線：</strong> {activeOrder.route?.join(' → ')}
                            </div>
                            <div className="text-sm text-gray-600 mt-1">
                                <strong>預計時間：</strong> {activeOrder.eta_sec?.toFixed(1)} 秒
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {robotState?.state === 'ARRIVED' && (
                <div className="mt-6 bg-green-50 border border-green-200 rounded-xl p-6 text-center">
                    <div className="text-4xl mb-2">🎉</div>
                    <h2 className="text-xl font-bold text-green-700">配送完成！</h2>
                    <p className="text-green-600 mt-1">您的餐點已送達</p>
                </div>
            )}
        </div>
    )
}
