import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Products from './pages/Products'
import Customers from './pages/Customers'
import Orders from './pages/Orders'
import Suppliers from './pages/Suppliers'
import Finance from './pages/Finance'
import { useBranch } from './context/BranchContext'

import { Toaster } from 'react-hot-toast'

import {
  LayoutDashboard,
  Box,
  ShoppingCart,
  Users,
  Truck,
  Wallet,
} from 'lucide-react'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/products', label: 'Products', icon: Box },
  { path: '/orders', label: 'Orders', icon: ShoppingCart },
  { path: '/customers', label: 'Customers', icon: Users },
  { path: '/suppliers', label: 'Suppliers', icon: Truck },
  { path: '/finance', label: 'Finance', icon: Wallet },
]

export default function App() {
  const { branches, selectedBranch, setSelectedBranch } = useBranch()

  return (
    <BrowserRouter>
      {/* ✅ Global Toast */}
      <Toaster position="top-right" />

      <div className="flex h-screen bg-gray-100">

        {/* Sidebar */}
        <aside className="w-64 bg-gray-900 text-white flex flex-col justify-between">
          <div>
            <div className="p-5 border-b border-gray-800">
              <h1 className="text-xl font-bold">Blacphics</h1>
              <p className="text-sm text-gray-400">Business Manager</p>
            </div>

            <nav className="p-3 space-y-2">
              {navItems.map(item => {
                const Icon = item.icon
                return (
                  <NavLink key={item.path} to={item.path}>
                    {({ isActive }) => (
                      <div
                        className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition ${
                          isActive
                            ? 'bg-indigo-600 text-white shadow border-l-4 border-white'
                            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                        }`}
                      >
                        <Icon size={18} />
                        <span>{item.label}</span>
                      </div>
                    )}
                  </NavLink>
                )
              })}
            </nav>
          </div>

          <div className="p-4 text-xs text-gray-500">
            v1.0.0
          </div>
        </aside>

        {/* RIGHT SIDE */}
        <div className="flex-1 flex flex-col">

          {/* ✅ Branch Selector */}
          <div className="p-3 flex gap-2 border-b bg-white overflow-x-auto">
            {branches.length === 0 ? (
              <span className="text-sm text-gray-400">No branches</span>
            ) : (
              branches.map(b => (
                <button
                  key={b.id}
                  onClick={() => setSelectedBranch(b)}
                  className={`px-3 py-1 rounded-full text-sm whitespace-nowrap ${
                    selectedBranch?.id === b.id
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {b.name}
                </button>
              ))
            )}
          </div>

          {/* Main Content */}
          <main className="flex-1 p-6 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/products" element={<Products />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/orders" element={<Orders />} />
              <Route path="/suppliers" element={<Suppliers />} />
              <Route path="/finance" element={<Finance />} />
            </Routes>
          </main>

        </div>
      </div>
    </BrowserRouter>
  )
}