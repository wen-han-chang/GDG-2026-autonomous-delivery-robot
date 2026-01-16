import { useCartStore } from '../stores/cartStore'

export default function ProductCard({ product }) {
    const addItem = useCartStore((state) => state.addItem)

    return (
        <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow">
            <div className="h-40 bg-gray-200 overflow-hidden">
                <img
                    src={product.image}
                    alt={product.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                        e.target.style.display = 'none'
                        e.target.parentElement.classList.add('flex', 'items-center', 'justify-center', 'bg-gradient-to-br', 'from-orange-100', 'to-orange-200')
                        e.target.parentElement.innerHTML = '<span class="text-6xl">📦</span>'
                    }}
                />
            </div>
            <div className="p-4">
                <h3 className="font-bold text-lg text-gray-800">{product.name}</h3>
                <p className="text-gray-500 text-sm mt-1">{product.description}</p>
                <div className="mt-4 flex items-center justify-between">
                    <span className="text-xl font-bold text-orange-600">${product.price}</span>
                    <button
                        onClick={() => addItem(product)}
                        className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg font-medium transition-colors cursor-pointer"
                    >
                        加入購物車
                    </button>
                </div>
            </div>
        </div>
    )
}
