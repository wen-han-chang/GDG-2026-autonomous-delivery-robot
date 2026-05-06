import { useEffect, useRef, useState, useCallback } from 'react'

const RETRY_DELAY_MS = 3000

export function useWebSocket(orderId, robotId) {
    const ws = useRef(null)
    const retryCount = useRef(0)
    const retryTimeout = useRef(null)
    const connectRef = useRef(null)
    const shouldReconnect = useRef(true)
    const [robotState, setRobotState] = useState(null)
    const [connected, setConnected] = useState(false)
    const [error, setError] = useState(null)

    const connect = useCallback(() => {
        if (!orderId) return

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/ws`
        ws.current = new WebSocket(wsUrl)

        ws.current.onopen = () => {
            setConnected(true)
            setError(null)
            retryCount.current = 0  // 連線成功，重置重試計數
            ws.current.send(JSON.stringify({
                type: 'subscribe',
                payload: { order_id: orderId }
            }))
        }

        ws.current.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)

                const sameOrder = data.order_id === orderId
                const sameRobot = !!robotId && data.robot_id === robotId
                if (data.type === 'order_update' && (sameOrder || sameRobot)) {
                    setRobotState({
                        node: data.node,
                        progress: data.progress,
                        speed: data.speed,
                        state: data.state
                    })
                }
            } catch (err) {
                console.error('WebSocket 訊息解析失敗:', err)
            }
        }

        ws.current.onclose = () => {
            setConnected(false)

            if (!shouldReconnect.current) {
                return
            }

            // 持續自動重連，避免進入永久失敗狀態
            retryCount.current += 1
            setError(`連線中斷，重試中（第 ${retryCount.current} 次）`)
            console.warn(`WebSocket 斷線，${RETRY_DELAY_MS / 1000} 秒後重連（第 ${retryCount.current} 次）`)
            retryTimeout.current = setTimeout(() => connectRef.current?.(), RETRY_DELAY_MS)
        }

        ws.current.onerror = () => {
            setConnected(false)
        }
    }, [orderId, robotId])

    useEffect(() => {
        connectRef.current = connect
    }, [connect])

    useEffect(() => {
        shouldReconnect.current = true
        connect()
        return () => {
            shouldReconnect.current = false
            // 清理：關閉連線並取消待執行的重連
            if (retryTimeout.current) {
                clearTimeout(retryTimeout.current)
            }
            if (ws.current) {
                ws.current.close()
            }
        }
    }, [connect])

    return { robotState, connected, error }
}