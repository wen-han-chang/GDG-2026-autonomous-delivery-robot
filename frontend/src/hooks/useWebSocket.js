import { useEffect, useRef, useState, useCallback } from 'react'

const MAX_RETRIES = 5
const RETRY_DELAY_MS = 3000

export function useWebSocket(orderId) {
    const ws = useRef(null)
    const retryCount = useRef(0)
    const retryTimeout = useRef(null)
    const connectRef = useRef(null)
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
            retryCount.current = 0  // 連線成功，重置重試次數
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

            // 自動重連機制
            if (retryCount.current < MAX_RETRIES) {
                retryCount.current += 1
                console.log(`WebSocket 斷線，${RETRY_DELAY_MS / 1000} 秒後重連 (${retryCount.current}/${MAX_RETRIES})`)
                retryTimeout.current = setTimeout(() => connectRef.current?.(), RETRY_DELAY_MS)
            } else {
                setError('連線失敗，請重新整理頁面')
                console.error('WebSocket 重連失敗，已達最大重試次數')
            }
        }

        ws.current.onerror = () => {
            setConnected(false)
        }
    }, [orderId])

    useEffect(() => {
        connectRef.current = connect
    }, [connect])

    useEffect(() => {
        connect()
        return () => {
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