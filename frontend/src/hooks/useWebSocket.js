import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket(orderId) {
    const ws = useRef(null)
    const [robotState, setRobotState] = useState(null)
    const [connected, setConnected] = useState(false)

    const connect = useCallback(() => {
        if (!orderId) return

        // ❌ 舊的寫法 (會連到 5173)
        // const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        // ws.current = new WebSocket(`${protocol}//${window.location.host}/ws`)

        // ✅ 新的寫法 (強制連到後端 8000)
        // 如果你有設定環境變數 VITE_API_URL，也可以用 replace('http', 'ws') 來做
        const wsUrl = 'ws://localhost:8000/ws'; 
        
        console.log("嘗試連線 WebSocket:", wsUrl); // 加個 log 方便除錯
        ws.current = new WebSocket(wsUrl)

        ws.current.onopen = () => {
            console.log("WebSocket 連線成功！");
            setConnected(true)
            ws.current.send(JSON.stringify({
                type: 'subscribe',
                payload: { order_id: orderId }
            }))
        }

        ws.current.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                // console.log("收到 WS 資料:", data); // 如果想看詳細資料可以打開這行
                
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
            console.log("WebSocket 連線關閉");
            setConnected(false)
        }

        ws.current.onerror = (err) => {
            console.error("WebSocket 發生錯誤:", err);
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