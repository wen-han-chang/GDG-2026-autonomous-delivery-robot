import { useState, useEffect } from 'react'
import StoreCard from '../components/StoreCard'

export default function Home() {
    const [stores, setStores] = useState([])
    const [loading, setLoading] = useState(true)
    const [selectedCategory, setSelectedCategory] = useState('全部')

    const categories = ['全部', '餐廳', '飲料', '便利商店']

    useEffect(() => {
        fetch('/stores.json')
            .then(res => res.json())
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
