import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'

const navItems = [
  { path: '/', label: 'Dashboard', icon: '▦' },
  { path: '/products', label: 'Products', icon: '◈' },
  { path: '/orders', label: 'Orders', icon: '◎' },
  { path: '/customers', label: 'Customers', icon: '◉' },
  { path: '/suppliers', label: 'Suppliers', icon: '◍' },
  { path: '/finance', label: 'Finance', icon: '◆' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-100">

        {/* Sidebar */}
        <aside className="w-64 bg-gray-900 text-white flex flex-col justify-between">

          {/* Top */}
          <div>
            <div className="p-5 border-b border-gray-800">
              <h1 className="text-xl font-bold">Blacphics</h1>
              <p className="text-sm text-gray-400">Business Manager</p>
            </div>

            {/* Navigation */}
            <nav className="p-3 space-y-2">
              {navItems.map(item => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                      isActive
                        ? 'bg-indigo-600 text-white'
                        : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                    }`
                  }
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Bottom */}
          <div className="p-4 text-xs text-gray-500">
            v1.0.0
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
          </Routes>
        </main>

      </div>
    </BrowserRouter>
  )
}