import { Link } from 'react-router-dom'

export default function StoreCard({ store }) {
    return (
        <Link
            to={`/store/${store.id}`}
            className="block bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow"
        >
            <div className="h-40 bg-gray-200 overflow-hidden">
                <img
                    src={store.image}
                    alt={store.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                        e.target.style.display = 'none'
                        e.target.parentElement.classList.add('flex', 'items-center', 'justify-center', 'bg-gradient-to-br', 'from-orange-400', 'to-orange-600')
                        e.target.parentElement.innerHTML = `<span class="text-6xl">${store.category === '餐廳' ? '🍱' : store.category === '飲料' ? '🧋' : '🏪'}</span>`
                    }}
                />
            </div>
            <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-lg font-bold text-gray-800">{store.name}</h3>
                    <span className="text-sm bg-orange-100 text-orange-600 px-2 py-1 rounded-full">
                        {store.category}
                    </span>
                </div>
                <p className="text-gray-500 text-sm mb-3">{store.description}</p>
                <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-1">
                        <span className="text-yellow-500">★</span>
                        <span className="font-medium">{store.rating}</span>
                    </div>
                    <span className="text-gray-400">{store.deliveryTime}</span>
                </div>
            </div>
        </Link>
    )
}
