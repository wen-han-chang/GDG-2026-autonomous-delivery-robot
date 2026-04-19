import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function Profile() {
    const { user, isLoggedIn, orderHistory, updateName, updatePassword, fetchOrderHistory, updateAvatar, fetchMe } = useAuthStore()
    const navigate = useNavigate()
    const fileInputRef = useRef(null)

    const [activeTab, setActiveTab] = useState('info')
    const [newName, setNewName] = useState(user?.name || '')
    const [oldPassword, setOldPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [message, setMessage] = useState({ type: '', text: '' })
    const [loading, setLoading] = useState(false)

    // 載入訂單歷史
    useEffect(() => {
        if (isLoggedIn) {
            fetchMe()
            fetchOrderHistory()
        } else {
            navigate('/login')
        }
    }, [isLoggedIn, fetchMe, fetchOrderHistory, navigate])

    const handleUpdateName = async (e) => {
        e.preventDefault()
        if (!newName.trim()) {
            setMessage({ type: 'error', text: '請輸入姓名' })
            return
        }
        setLoading(true)
        const result = await updateName(newName)
        setLoading(false)
        if (result.success) {
            setMessage({ type: 'success', text: '姓名已更新' })
        } else {
            setMessage({ type: 'error', text: result.error })
        }
    }

    const handleUpdatePassword = async (e) => {
        e.preventDefault()
        setMessage({ type: '', text: '' })

        if (newPassword !== confirmPassword) {
            setMessage({ type: 'error', text: '新密碼不一致' })
            return
        }

        // 密碼驗證
        const hasUpperCase = /[A-Z]/.test(newPassword)
        const hasLowerCase = /[a-z]/.test(newPassword)
        const digitCount = (newPassword.match(/\d/g) || []).length

        if (!hasUpperCase || !hasLowerCase || digitCount < 6) {
            setMessage({ type: 'error', text: '密碼需包含大小寫字母各一個及 6 個以上數字' })
            return
        }

        setLoading(true)
        const result = await updatePassword(oldPassword, newPassword)
        setLoading(false)
        if (result.success) {
            setMessage({ type: 'success', text: '密碼已更新' })
            setOldPassword('')
            setNewPassword('')
            setConfirmPassword('')
        } else {
            setMessage({ type: 'error', text: result.error })
        }
    }

    const handleAvatarClick = () => {
        fileInputRef.current?.click()
    }

    const handleAvatarChange = async (e) => {
        const file = e.target.files[0]
        if (!file) return
        const reader = new FileReader()
        reader.onload = async (ev) => {
            await updateAvatar(ev.target.result)
        }
        reader.readAsDataURL(file)
    }

    const formatDate = (dateStr) => {
        const date = new Date(dateStr)
        return date.toLocaleDateString('zh-TW', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })
    }

    return (
        <div className="max-w-4xl mx-auto px-4 py-8">
            <Link to="/" className="text-orange-600 hover:text-orange-700 mb-6 inline-block">
                ← 返回首頁
            </Link>

            <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
                {/* Header */}
                <div className="bg-gradient-to-r from-orange-500 to-orange-600 p-6 text-white">
                    <div className="flex items-center gap-4">
                        <div
                            className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center text-3xl cursor-pointer overflow-hidden relative group"
                            onClick={handleAvatarClick}
                            title="點擊更換頭像"
                        >
                            {user?.avatar
                                ? <img src={user.avatar} alt="avatar" className="w-full h-full object-cover" />
                                : <span>👤</span>
                            }
                            <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                                <span className="text-white text-xs">更換</span>
                            </div>
                        </div>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={handleAvatarChange}
                        />
                        <div>
                            <h1 className="text-2xl font-bold">{user?.name}</h1>
                            <p className="text-orange-100">{user?.email}</p>
                        </div>
                    </div>
                </div>

                {/* Tabs */}
                <div className="border-b border-gray-200">
                    <div className="flex">
                        <button
                            onClick={() => setActiveTab('info')}
                            className={`px-6 py-3 font-medium cursor-pointer transition-colors ${activeTab === 'info'
                                ? 'text-orange-600 border-b-2 border-orange-600'
                                : 'text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            帳號資訊
                        </button>
                        <button
                            onClick={() => setActiveTab('orders')}
                            className={`px-6 py-3 font-medium cursor-pointer transition-colors ${activeTab === 'orders'
                                ? 'text-orange-600 border-b-2 border-orange-600'
                                : 'text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            訂單記錄
                        </button>
                        <button
                            onClick={() => setActiveTab('settings')}
                            className={`px-6 py-3 font-medium cursor-pointer transition-colors ${activeTab === 'settings'
                                ? 'text-orange-600 border-b-2 border-orange-600'
                                : 'text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            修改資料
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6">
                    {message.text && (
                        <div className={`mb-4 p-3 rounded-lg text-sm ${message.type === 'success'
                            ? 'bg-green-50 text-green-600'
                            : 'bg-red-50 text-red-600'
                            }`}>
                            {message.text}
                        </div>
                    )}

                    {/* 帳號資訊 */}
                    {activeTab === 'info' && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-gray-50 p-4 rounded-lg">
                                    <div className="text-sm text-gray-500">姓名</div>
                                    <div className="font-medium text-gray-800">{user?.name}</div>
                                </div>
                                <div className="bg-gray-50 p-4 rounded-lg min-w-0">
                                    <div className="text-sm text-gray-500">Email</div>
                                    <div className="font-medium text-gray-800 truncate">{user?.email}</div>
                                </div>
                                <div className="bg-gray-50 p-4 rounded-lg min-w-0">
                                    <div className="text-sm text-gray-500">帳號 ID</div>
                                    <div className="font-medium text-gray-800 truncate">{user?.id}</div>
                                </div>
                                <div className="bg-gray-50 p-4 rounded-lg">
                                    <div className="text-sm text-gray-500">註冊時間</div>
                                    <div className="font-medium text-gray-800">
                                        {user?.createdAt ? formatDate(user.createdAt) : '未知'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 訂單記錄 */}
                    {activeTab === 'orders' && (
                        <div className="space-y-4">
                            {orderHistory.length === 0 ? (
                                <div className="text-center text-gray-500 py-8">
                                    尚無訂單記錄
                                </div>
                            ) : (
                                orderHistory.map((order) => (
                                    <div key={order.id} className="border border-gray-200 rounded-lg p-4">
                                        <div className="flex justify-between items-start mb-2">
                                            <div>
                                                <span className="font-medium text-gray-800">#{order.id}</span>
                                            </div>
                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${order.status === '已完成'
                                                ? 'bg-green-100 text-green-600'
                                                : 'bg-orange-100 text-orange-600'
                                                }`}>
                                                {order.status}
                                            </span>
                                        </div>
                                        <div className="text-sm text-gray-500 mb-2">{order.date}</div>
                                        <div className="text-sm text-gray-600">
                                            {order.items.join('、')}
                                        </div>
                                        <div className="mt-2 text-right font-bold text-orange-600">
                                            ${order.total}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}

                    {/* 修改資料 */}
                    {activeTab === 'settings' && (
                        <div className="space-y-8">
                            {/* 修改姓名 */}
                            <form onSubmit={handleUpdateName} className="space-y-4">
                                <h3 className="font-bold text-gray-800">修改姓名</h3>
                                <div className="flex gap-3">
                                    <input
                                        type="text"
                                        value={newName}
                                        onChange={(e) => setNewName(e.target.value)}
                                        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                                        placeholder="新姓名"
                                    />
                                    <button
                                        type="submit"
                                        disabled={loading}
                                        className="px-6 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors cursor-pointer disabled:opacity-50"
                                    >
                                        {loading ? '更新中...' : '更新'}
                                    </button>
                                </div>
                            </form>

                            <hr className="border-gray-200" />

                            {/* 修改密碼 */}
                            <form onSubmit={handleUpdatePassword} className="space-y-4">
                                <h3 className="font-bold text-gray-800">修改密碼</h3>
                                <input
                                    type="password"
                                    value={oldPassword}
                                    onChange={(e) => setOldPassword(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                                    placeholder="目前密碼"
                                    required
                                />
                                <input
                                    type="password"
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                                    placeholder="新密碼"
                                    required
                                />
                                <p className="text-xs text-gray-500">
                                    ⚠️ 密碼需包含：至少一個大寫字母、一個小寫字母、以及 6 個以上數字
                                </p>
                                <input
                                    type="password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
                                    placeholder="確認新密碼"
                                    required
                                />
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="px-6 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors cursor-pointer disabled:opacity-50"
                                >
                                    {loading ? '更新中...' : '更新密碼'}
                                </button>
                            </form>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
