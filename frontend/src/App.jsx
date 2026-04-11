import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Dashboard from './pages/Dashboard'
import Products from './pages/Products'
import Customers from './pages/Customers'
import Orders from './pages/Orders'
import Suppliers from './pages/Suppliers'
import Finance from './pages/Finance'
import POS from './pages/POS'
import Alerts from './pages/Alerts'
import { useBranch } from './context/BranchContext'
import { getAlerts } from './api/api'
import { Toaster } from 'react-hot-toast'
import {
  LayoutDashboard, Box, ShoppingCart,
  Users, Truck, Wallet, CreditCard, Bell,
} from 'lucide-react'

export default function App() {
  const { branches, selectedBranch, setSelectedBranch } = useBranch()
  const [alertCount, setAlertCount] = useState(0)

  // Poll alerts every 60 seconds for badge count
  useEffect(() => {
    if (!selectedBranch) return
    const fetch = () => {
      getAlerts(selectedBranch.id)
        .then(r => setAlertCount(r.data.count || 0))
        .catch(() => {})
    }
    fetch()
    const interval = setInterval(fetch, 60000)
    return () => clearInterval(interval)
  }, [selectedBranch])

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/pos', label: 'POS', icon: CreditCard },
    { path: '/products', label: 'Products', icon: Box },
    { path: '/orders', label: 'Orders', icon: ShoppingCart },
    { path: '/customers', label: 'Customers', icon: Users },
    { path: '/suppliers', label: 'Suppliers', icon: Truck },
    { path: '/finance', label: 'Finance', icon: Wallet },
    { path: '/alerts', label: 'Alerts', icon: Bell, badge: alertCount },
  ]

  return (
    <BrowserRouter>
      <Toaster position="top-right" />
      <div className="flex h-screen bg-gray-100">

        <aside className="w-64 bg-gray-900 text-white flex flex-col justify-between">
          <div>
            <div className="p-5 border-b border-gray-800">
              <h1 className="text-xl font-bold">Blacphics</h1>
              <p className="text-sm text-gray-400">Business Manager</p>
            </div>
            <nav className="p-3 space-y-1">
              {navItems.map(item => {
                const Icon = item.icon
                return (
                  <NavLink key={item.path} to={item.path}>
                    {({ isActive }) => (
                      <div className={`flex items-center justify-between px-4 py-2.5 rounded-lg text-sm transition ${
                        isActive ? 'bg-indigo-600 text-white shadow border-l-4 border-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                      }`}>
                        <div className="flex items-center gap-3">
                          <Icon size={18} />
                          <span>{item.label}</span>
                        </div>
                        {item.badge > 0 && (
                          <span className="bg-rose-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
                            {item.badge > 99 ? '99+' : item.badge}
                          </span>
                        )}
                      </div>
                    )}
                  </NavLink>
                )
              })}
            </nav>
          </div>
          <div className="p-4 text-xs text-gray-500">v1.0.0</div>
        </aside>

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="p-3 flex gap-2 border-b bg-white overflow-x-auto shrink-0">
            {branches.length === 0 ? (
              <span className="text-sm text-gray-400">No branches</span>
            ) : branches.map(b => (
              <button key={b.id} onClick={() => setSelectedBranch(b)}
                className={`px-3 py-1 rounded-full text-sm whitespace-nowrap ${
                  selectedBranch?.id === b.id ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-600'
                }`}>
                {b.name}
              </button>
            ))}
          </div>

          <main className="flex-1 overflow-hidden flex flex-col">
            <Routes>
              <Route path="/" element={<div className="flex-1 overflow-auto p-6"><Dashboard /></div>} />
              <Route path="/products" element={<div className="flex-1 overflow-auto p-6"><Products /></div>} />
              <Route path="/customers" element={<div className="flex-1 overflow-auto p-6"><Customers /></div>} />
              <Route path="/orders" element={<div className="flex-1 overflow-auto p-6"><Orders /></div>} />
              <Route path="/suppliers" element={<div className="flex-1 overflow-auto p-6"><Suppliers /></div>} />
              <Route path="/finance" element={<div className="flex-1 overflow-auto p-6"><Finance /></div>} />
              <Route path="/alerts" element={<div className="flex-1 overflow-auto p-6"><Alerts /></div>} />
              <Route path="/pos" element={<div className="flex-1 overflow-hidden flex flex-col h-full"><POS /></div>} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}