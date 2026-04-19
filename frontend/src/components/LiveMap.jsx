import { useEffect, useRef } from 'react'

export default function LiveMap({ mapData, robotPosition, route, size = 'lg' }) {
    const canvasRef = useRef(null)

    useEffect(() => {
        if (!mapData || !canvasRef.current) return

        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')
        const scale = 2
        const offsetX = 50
        const offsetY = 50

        // 將地圖座標轉為 canvas 座標（y 從最小值開始正規化）
        const yMin = Math.min(...mapData.nodes.map(n => n.y))
        const toCanvas = (node) => ({
            x: node.x * scale + offsetX,
            y: (node.y - yMin) * scale + offsetY,
        })

        ctx.clearRect(0, 0, canvas.width, canvas.height)

        // 畫邊線
        ctx.strokeStyle = '#e5e7eb'
        ctx.lineWidth = 8
        ctx.lineCap = 'round'

        if (mapData.edges) {
            mapData.edges.forEach(edge => {
                const from = mapData.nodes.find(n => n.id === edge.from)
                const to = mapData.nodes.find(n => n.id === edge.to)
                if (from && to) {
                    const cf = toCanvas(from)
                    const ct = toCanvas(to)
                    ctx.beginPath()
                    ctx.moveTo(cf.x, cf.y)
                    ctx.lineTo(ct.x, ct.y)
                    ctx.stroke()
                }
            })
        }

        // 標示路線
        if (route && route.length > 1) {
            ctx.strokeStyle = '#f97316'
            ctx.lineWidth = 6
            for (let i = 0; i < route.length - 1; i++) {
                const from = mapData.nodes.find(n => n.id === route[i])
                const to = mapData.nodes.find(n => n.id === route[i + 1])
                if (from && to) {
                    const cf = toCanvas(from)
                    const ct = toCanvas(to)
                    ctx.beginPath()
                    ctx.moveTo(cf.x, cf.y)
                    ctx.lineTo(ct.x, ct.y)
                    ctx.stroke()
                }
            }
        }

        // 畫節點
        mapData.nodes.forEach(node => {
            const { x, y } = toCanvas(node)

            ctx.fillStyle = route?.includes(node.id) ? '#f97316' : '#374151'
            ctx.beginPath()
            ctx.arc(x, y, 12, 0, Math.PI * 2)
            ctx.fill()

            ctx.fillStyle = '#374151'
            ctx.font = 'bold 13px sans-serif'
            ctx.textAlign = 'center'
            ctx.fillText(node.name || node.id, x, y + 28)
        })

        // 畫機器人
        if (robotPosition) {
            const node = mapData.nodes.find(n => n.id === robotPosition.node)
            if (node) {
                const { x, y } = toCanvas(node)
                ctx.fillStyle = '#ef4444'
                ctx.beginPath()
                ctx.arc(x, y, 16, 0, Math.PI * 2)
                ctx.fill()

                ctx.fillStyle = 'white'
                ctx.font = '16px sans-serif'
                ctx.textAlign = 'center'
                ctx.textBaseline = 'middle'
                ctx.fillText('🚗', x, y)
            }
        }
    }, [mapData, robotPosition, route])

    return (
        <div className="bg-gray-50 rounded-xl p-4">
            <canvas
                ref={canvasRef}
                width={450}
                height={450}
                className={size === 'sm' ? 'max-w-[300px] mx-auto block' : 'w-full'}
            />
        </div>
    )
}
