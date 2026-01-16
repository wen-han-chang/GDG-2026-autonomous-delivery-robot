import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import Store from './pages/Store'
import Cart from './pages/Cart'
import Checkout from './pages/Checkout'
import Tracking from './pages/Tracking'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100">
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/store/:storeId" element={<Store />} />
          <Route path="/cart" element={<Cart />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/tracking/:orderId" element={<Tracking />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
