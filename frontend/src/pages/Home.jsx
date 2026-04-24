import { useState, useEffect } from 'react'
import StoreCard from '../components/StoreCard'
import { useRobotStatus } from '../hooks/useRobotStatus'

export default function Home() {
    const [stores, setStores] = useState([])
    const [loading, setLoading] = useState(true)
    const [selectedCategory, setSelectedCategory] = useState('全部')
    const { status, isIdle } = useRobotStatus('R001')

    const categories = ['全部', '餐廳', '飲料', '便利商店']

    useEffect(() => {
        // 從環境變數讀取後端網址
        const apiUrl = import.meta.env.VITE_API_URL;
        
        // 使用絕對路徑連往後端
        fetch(`${apiUrl}/stores`)
            .then(res => {
                if (!res.ok) throw new Error('Network response was not ok');
                return res.json();
            })
            .then(data => {
                setStores(data)
                setLoading(false)
            })
            .catch(err => {
                console.error('Failed to load stores:', err)
                setLoading(false)
            })
    }, [])

    const filteredStores = selectedCategory === '全部'
        ? stores
        : stores.filter(store => store.category === selectedCategory)

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[50vh]">
                <div className="text-xl text-gray-500">載入中...</div>
            </div>
        )
    }

    return (
        <div className="max-w-6xl mx-auto px-4 py-8">
            {status && (
                <div className={`flex items-center gap-3 mb-6 px-4 py-3 rounded-xl text-sm font-medium ${
                    isIdle
                        ? 'bg-green-50 text-green-700 border border-green-200'
                        : 'bg-orange-50 text-orange-700 border border-orange-200'
                }`}>
                    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${isIdle ? 'bg-green-500' : 'bg-orange-500 animate-pulse'}`} />
                    <span>{isIdle ? '送餐車待命中，可以下單' : `送餐車配送中（${status.pending_count} 筆訂單待完成）`}</span>
                    <span className="ml-auto text-xs opacity-60">目前位置：{status.current_node ?? '—'}</span>
                </div>
            )}

            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-800">探索店家</h1>
                <p className="text-gray-500 mt-2">選擇您喜愛的店家，開始點餐</p>
            </div>

            <div className="flex gap-3 mb-6 overflow-x-auto pb-2">
                {categories.map(category => (
                    <button
                        key={category}
                        onClick={() => setSelectedCategory(category)}
                        className={`px-4 py-2 rounded-full font-medium whitespace-nowrap transition-colors cursor-pointer ${selectedCategory === category
                            ? 'bg-orange-500 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                    >
                        {category}
                    </button>
                ))}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredStores.map(store => (
                    <StoreCard key={store.id} store={store} />
                ))}
            </div>

            {filteredStores.length === 0 && (
                <div className="text-center text-gray-500 py-12">
                    沒有符合的店家
                </div>
            )}
        </div>
    )
}
