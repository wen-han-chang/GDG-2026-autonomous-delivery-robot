import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useCartStore } from '../stores/cartStore'
import { useAuthStore } from '../stores/authStore'

export default function Navbar() {
    const itemCount = useCartStore((state) => state.getItemCount())
    const clearCart = useCartStore((state) => state.clearCart)
    const { user, isLoggedIn, logout } = useAuthStore()
    const [showLogoutModal, setShowLogoutModal] = useState(false)
    const navigate = useNavigate()

    const handleLogout = () => {
        logout()
        clearCart()  // 登出時清空購物車
        setShowLogoutModal(false)
        navigate('/')
    }

    return (
        <>
            <nav className="bg-white shadow-md sticky top-0 z-50">
                <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
                    <Link to="/" className="text-2xl font-bold text-orange-600 flex items-center gap-2">
                        <span>DeliveryBot</span>
                    </Link>

                    <div className="flex items-center gap-4">
                        {isLoggedIn ? (
                            <div className="flex items-center gap-3">
                                <Link
                                    to="/profile"
                                    className="text-gray-600 hover:text-orange-600 text-sm flex items-center gap-2 transition-colors"
                                >
                                    <div className="w-7 h-7 rounded-full overflow-hidden bg-gray-200 flex items-center justify-center text-sm">
                                        {user?.avatar
                                            ? <img src={user.avatar} alt="avatar" className="w-full h-full object-cover" />
                                            : <span>👤</span>
                                        }
                                    </div>
                                    {user?.name}
                                </Link>
                                <button
                                    onClick={() => setShowLogoutModal(true)}
                                    className="text-gray-500 hover:text-gray-700 text-sm cursor-pointer"
                                >
                                    登出
                                </button>
                            </div>
                        ) : (
                            <Link
                                to="/login"
                                className="text-orange-600 hover:text-orange-700 font-medium"
                            >
                                登入
                            </Link>
                        )}

                        <Link
                            to="/cart"
                            className="relative bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                        >
                            🛒
                            {itemCount > 0 && (
                                <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs w-6 h-6 rounded-full flex items-center justify-center font-bold">
                                    {itemCount}
                                </span>
                            )}
                        </Link>
                    </div>
                </div>
            </nav>

            {/* Logout Confirmation Modal */}
            {showLogoutModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl">
                        <h3 className="text-lg font-bold text-gray-800 mb-2">確認登出</h3>
                        <p className="text-gray-600 mb-6">您確定要登出嗎？</p>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowLogoutModal(false)}
                                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer"
                            >
                                取消
                            </button>
                            <button
                                onClick={handleLogout}
                                className="flex-1 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-colors cursor-pointer"
                            >
                                確認登出
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
