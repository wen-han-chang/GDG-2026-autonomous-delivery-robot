import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import LiveMap from '../components/LiveMap'

const apiUrl = import.meta.env.VITE_API_URL

export default function Store() {
    const { storeId } = useParams()
    const [store, setStore] = useState(null)
    const [products, setProducts] = useState([])
    const [mapData, setMapData] = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        Promise.all([
            fetch(`${apiUrl}/stores/${storeId}`).then(res => res.json()),
            fetch(`${apiUrl}/stores/${storeId}/products`).then(res => res.json()),
            fetch('/map.json').then(res => res.json()).catch(() => null)
        ])
            .then(([storeData, productsData, mapJson]) => {
                setStore(storeData)
                setProducts(productsData)
                setMapData(mapJson)
                setLoading(false)
            })
            .catch(err => {
                console.error('Failed to load data:', err)
                setLoading(false)
            })
    }, [storeId])

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[50vh]">
                <div className="text-xl text-gray-500">載入中...</div>
            </div>
        )
    }

    if (!store) {
        return (
            <div className="max-w-6xl mx-auto px-4 py-8 text-center">
                <h1 className="text-2xl font-bold text-gray-800">店家不存在</h1>
                <Link to="/" className="text-orange-600 hover:underline mt-4 inline-block">
                    返回首頁
                </Link>
            </div>
        )
    }

    return (
        <div className="max-w-6xl mx-auto px-4 py-8">
            <Link to="/" className="text-orange-600 hover:text-orange-700 mb-6 inline-block">
                ← 返回店家列表
            </Link>

            <div className="bg-white rounded-xl shadow-md p-6 mb-8">
                <div className="flex items-center gap-4">
                    <div className="w-20 h-20 bg-gray-200 rounded-xl overflow-hidden">
                        <img
                            src={store.image}
                            alt={store.name}
                            className="w-full h-full object-cover"
                        />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-800">{store.name}</h1>
                        <p className="text-gray-500">{store.description}</p>
                        <div className="flex items-center gap-4 mt-2 text-sm">
                            <span className="flex items-center gap-1">
                                <span className="text-yellow-500">★</span>
                                <span className="font-medium">{store.rating}</span>
                            </span>
                            <span className="text-gray-400">|</span>
                            <span className="text-gray-500">{store.deliveryTime}</span>
                        </div>
                    </div>
                </div>
            </div>

            <h2 className="text-xl font-bold text-gray-800 mb-4">菜單</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {products.map(product => (
                    <ProductCard
                        key={product.id}
                        product={{ ...product, store_name: store.name, store_id: storeId }}
                    />
                ))}
            </div>

            {mapData && store?.location_node && (
                <div className="bg-white rounded-xl shadow-md p-6 mt-8">
                    <h2 className="text-lg font-bold text-gray-800 mb-3">店家位置</h2>
                    <LiveMap
                        mapData={mapData}
                        route={[store.location_node]}
                        robotPosition={null}
                        size="sm"
                    />
                    <p className="text-sm text-gray-500 mt-2 text-center">節點 {store.location_node}</p>
                </div>
            )}

            {products.length === 0 && (
                <div className="text-center text-gray-500 py-12">
                    暫無商品
                </div>
            )}
        </div>
    )
}
