import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function Register() {
    const [name, setName] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const register = useAuthStore((state) => state.register)
    const navigate = useNavigate()

    // 密碼驗證：至少一個大寫、一個小寫、6個數字
    const validatePassword = (pwd) => {
        const hasUpperCase = /[A-Z]/.test(pwd)
        const hasLowerCase = /[a-z]/.test(pwd)
        const digitCount = (pwd.match(/\d/g) || []).length

        if (!hasUpperCase) return '密碼需包含至少一個大寫英文字母'
        if (!hasLowerCase) return '密碼需包含至少一個小寫英文字母'
        if (digitCount < 6) return '密碼需包含至少 6 個數字'
        return null
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setError('')

        if (password !== confirmPassword) {
            setError('密碼不一致')
            setLoading(false)
            return
        }

        const passwordError = validatePassword(password)
        if (passwordError) {
            setError(passwordError)
            setLoading(false)
            return
        }

        const result = await register(email, password, name)

        if (result.success) {
            navigate('/')
        } else {
            setError(result.error)
        }
        setLoading(false)
    }

    return (
        <div className="min-h-[80vh] flex items-center justify-center px-4">
            <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold text-gray-800">建立帳號</h1>
                    <p className="text-gray-500 mt-2">加入 DeliveryBot</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            姓名
                        </label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition"
                            placeholder="您的姓名"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Email
                        </label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition"
                            placeholder="your@email.com"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            密碼
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition"
                            placeholder="輸入密碼"
                            required
                        />
                        <p className="mt-2 text-xs text-gray-500">
                            *密碼需包含：至少一個大寫字母、一個小寫字母、以及 6 個以上數字
                        </p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            確認密碼
                        </label>
                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition"
                            placeholder="再次輸入密碼"
                            required
                        />
                    </div>

                    {error && (
                        <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-gray-400 text-white py-3 rounded-lg font-bold text-lg transition-colors cursor-pointer"
                    >
                        {loading ? '註冊中...' : '註冊'}
                    </button>
                </form>

                <div className="mt-6 text-center text-gray-500">
                    已有帳號？{' '}
                    <Link to="/login" className="text-orange-600 hover:underline font-medium">
                        登入
                    </Link>
                </div>
            </div>
        </div>
    )
}
