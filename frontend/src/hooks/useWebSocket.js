import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket(orderId) {
    const ws = useRef(null)
    const [robotState, setRobotState] = useState(null)
    const [connected, setConnected] = useState(false)

    const connect = useCallback(() => {
        if (!orderId) return

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        ws.current = new WebSocket(`${protocol}//${window.location.host}/ws`)

        ws.current.onopen = () => {
            setConnected(true)
            ws.current.send(JSON.stringify({
                type: 'subscribe',
                payload: { order_id: orderId }
            }))
        }

        ws.current.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                if (data.type === 'order_update' && data.order_id === orderId) {
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
        }

        ws.current.onerror = () => {
            setConnected(false)
        }
    }, [orderId])

    useEffect(() => {
        connect()
        return () => {
            if (ws.current) {
                ws.current.close()
            }
        }
    }, [connect])

    return { robotState, connected }
}
