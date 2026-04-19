import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCartStore } from '../stores/cartStore'
import { useOrderStore } from '../stores/orderStore'
import { useAuthStore } from '../stores/authStore'
import { createOrder } from '../api/orders'

export default function Checkout() {
    const [nodes, setNodes] = useState([])
    const [selectedNode, setSelectedNode] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [submitted, setSubmitted] = useState(false)

    const items = useCartStore((state) => state.items)
    const getTotal = useCartStore((state) => state.getTotal)
    const clearCart = useCartStore((state) => state.clearCart)
    const setOrder = useOrderStore((state) => state.setOrder)
    const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const navigate = useNavigate()

    useEffect(() => {
        fetch('/nodes.json')
            .then(res => res.json())
            .then(data => {
                setNodes(data)
                if (data.length > 0) {
                    setSelectedNode(data[0].id)
                }
            })
    }, [])

    const handleSubmit = async () => {
        if (!selectedNode) {
            setError('請選擇配送地點')
            return
        }

        setLoading(true)
        setError('')

        try {
            // 組裝訂單資訊
            const orderInfo = {
                storeName: items[0]?.store_name || '未知店家',
                items: items.map(item => `${item.name} x${item.quantity}`),
                total: getTotal(),
            }
            const token = useAuthStore.getState().token

            const storeId = items[0]?.store_id || null
            const order = await createOrder('campus_demo', storeId, selectedNode, orderInfo, token)
            setOrder(order)
            setSubmitted(true)
            clearCart()
            navigate(`/tracking/${order.order_id}`)
        } catch (err) {
            setError('下單失敗，請稍後再試')
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    // Redirect to login if not logged in
    if (!isLoggedIn) {
        navigate('/login')
        return null
    }

    // Only redirect to cart if not submitted and cart is empty
    if (!submitted && items.length === 0) {
        navigate('/cart')
        return null
    }

    return (
        <div className="max-w-2xl mx-auto px-4 py-8">
            <h1 className="text-2xl font-bold text-gray-800 mb-6">結帳</h1>

            {/* Delivery Location */}
            <div className="bg-white rounded-xl shadow-md p-6 mb-6">
                <h2 className="text-lg font-bold text-gray-800 mb-4">選擇配送地點</h2>
                <div className="space-y-3">
                    {nodes.map(node => (
                        <label
                            key={node.id}
                            className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-colors ${selectedNode === node.id
                                ? 'border-orange-500 bg-orange-50'
                                : 'border-gray-200 hover:border-orange-300'
                                }`}
                        >
                            <input
                                type="radio"
                                name="node"
                                value={node.id}
                                checked={selectedNode === node.id}
                                onChange={(e) => setSelectedNode(e.target.value)}
                                className="w-5 h-5 text-orange-500"
                            />
                            <div className="ml-3">
                                <div className="font-medium text-gray-800">{node.name}</div>
                                <div className="text-sm text-gray-500">節點 {node.id}</div>
                            </div>
                        </label>
                    ))}
                </div>
            </div>

            {/* Order Summary */}
            <div className="bg-white rounded-xl shadow-md p-6 mb-6">
                <h2 className="text-lg font-bold text-gray-800 mb-4">訂單明細</h2>
                <div className="space-y-2">
                    {items.map(item => (
                        <div key={item.id} className="flex justify-between text-gray-600">
                            <span>{item.name} x {item.quantity}</span>
                            <span>${item.price * item.quantity}</span>
                        </div>
                    ))}
                    <div className="border-t border-gray-200 pt-3 mt-3">
                        <div className="flex justify-between text-lg font-bold">
                            <span>總計</span>
                            <span className="text-orange-600">${getTotal()}</span>
                        </div>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-4">
                    {error}
                </div>
            )}

            <button
                onClick={handleSubmit}
                disabled={loading}
                className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-gray-400 text-white py-4 rounded-xl font-bold text-lg transition-colors cursor-pointer"
            >
                {loading ? '處理中...' : '確認下單'}
            </button>
        </div>
    )
}
