import { NavLink, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import {
  LayoutDashboard, Box, ShoppingCart, Users, Truck, Wallet,
  CreditCard, Bell, LogOut, ChevronRight, Sparkles,
} from 'lucide-react'
import { Toaster } from 'react-hot-toast'
import useAuth from '../../auth/useAuth'
import { useBranch } from '../../context/BranchContext'
import { getAlerts } from '../../api/api'
import BranchSelect from '../ui/BranchSelect'
import { initials } from '../../lib/format'

const navItems = [
  { path: '/', label: 'Home', icon: LayoutDashboard, end: true },
  { path: '/pos', label: 'Point of Sale', icon: CreditCard },
  { path: '/products', label: 'Products', icon: Box },
  { path: '/orders', label: 'Orders', icon: ShoppingCart },
  { path: '/customers', label: 'Customers', icon: Users },
  { path: '/suppliers', label: 'Suppliers', icon: Truck },
  { path: '/finance', label: 'Finance', icon: Wallet },
  { path: '/alerts', label: 'Alerts', icon: Bell, badgeKey: 'alerts' },
]

const pageTitles = {
  '/': 'Home',
  '/pos': 'Point of Sale',
  '/products': 'Products',
  '/orders': 'Orders',
  '/customers': 'Customers',
  '/suppliers': 'Suppliers',
  '/finance': 'Finance',
  '/alerts': 'Alerts',
}

export default function AppShell({ children }) {
  const { user, logout } = useAuth()
  const { selectedBranch } = useBranch()
  const location = useLocation()
  const [alertCount, setAlertCount] = useState(0)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  useEffect(() => {
    if (!selectedBranch) return
    const fetchAlerts = () => {
      getAlerts(selectedBranch.id)
        .then((r) => setAlertCount(r.data.count || 0))
        .catch(() => {})
    }
    fetchAlerts()
    const interval = setInterval(fetchAlerts, 60000)
    return () => clearInterval(interval)
  }, [selectedBranch])

  const displayName = user?.first_name
    ? `${user.first_name} ${user.last_name || ''}`.trim()
    : user?.username || 'User'

  const breadcrumb = pageTitles[location.pathname] || 'Blacphics'

  return (
    <div className="flex h-screen bg-[#f6f6f7]">
      <Toaster
        position="top-center"
        toastOptions={{
          className: 'text-sm font-medium',
          style: {
            borderRadius: '10px',
            border: '1px solid #e1e3e5',
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          },
          success: { iconTheme: { primary: '#008060', secondary: '#fff' } },
        }}
      />

      {/* Sidebar — Shopify-style light nav */}
      <aside className="hidden w-[240px] shrink-0 flex-col border-r border-[#e1e3e5] bg-[#ebebeb] md:flex md:flex-col">
        <div className="border-b border-[#e1e3e5] px-4 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#008060] text-white shadow-sm">
              <Sparkles size={18} />
            </div>
            <div>
              <p className="text-sm font-semibold text-[#202223] leading-tight">Blacphics</p>
              <p className="text-[11px] text-[#6d7175]">Business Manager</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon
            const badge = item.badgeKey === 'alerts' ? alertCount : 0
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                className={({ isActive }) =>
                  `group flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-[13px] font-medium transition ${
                    isActive
                      ? 'bg-white text-[#202223] shadow-sm'
                      : 'text-[#44474a] hover:bg-white/60 hover:text-[#202223]'
                  }`
                }
              >
                <span className="flex items-center gap-2.5">
                  <Icon size={18} strokeWidth={1.75} className="opacity-80" />
                  {item.label}
                </span>
                {badge > 0 && (
                  <span className="rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-bold text-white min-w-[18px] text-center">
                    {badge > 99 ? '99+' : badge}
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>

        <div className="border-t border-[#e1e3e5] p-3">
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-[#6d7175] transition hover:bg-white/60 hover:text-[#202223]"
          >
            <LogOut size={18} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex shrink-0 items-center gap-3 border-b border-[#e1e3e5] bg-white px-4 py-2.5 sm:px-5">
          <div className="flex min-w-0 flex-1 items-center gap-2 text-sm text-[#6d7175]">
            <span className="hidden font-medium text-[#202223] sm:inline">Blacphics</span>
            <ChevronRight size={14} className="hidden sm:block opacity-50" />
            <span className="truncate font-semibold text-[#202223]">{breadcrumb}</span>
            {selectedBranch && (
              <>
                <ChevronRight size={14} className="hidden opacity-50 md:block" />
                <span className="hidden truncate text-[#6d7175] md:inline">{selectedBranch.name}</span>
              </>
            )}
          </div>

          <BranchSelect className="hidden sm:block" />

          <div className="relative">
            <button
              type="button"
              onClick={() => setUserMenuOpen((o) => !o)}
              className="flex items-center gap-2 rounded-lg border border-[#e1e3e5] bg-[#fafbfb] py-1.5 pl-1.5 pr-2.5 transition hover:bg-[#f1f2f4]"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[#008060] text-xs font-semibold text-white">
                {initials(displayName)}
              </span>
              <span className="hidden max-w-[120px] truncate text-sm font-medium text-[#202223] lg:block">
                {displayName}
              </span>
            </button>
            {userMenuOpen && (
              <>
                <button
                  type="button"
                  className="fixed inset-0 z-40"
                  aria-label="Close menu"
                  onClick={() => setUserMenuOpen(false)}
                />
                <div className="absolute right-0 top-full z-50 mt-1 w-52 rounded-xl border border-[#e1e3e5] bg-white py-1 shadow-lg">
                  <div className="border-b border-[#e1e3e5] px-4 py-3">
                    <p className="text-sm font-semibold text-[#202223]">{displayName}</p>
                    <p className="text-xs text-[#6d7175]">{user?.email || user?.username}</p>
                  </div>
                  <div className="p-2 sm:hidden">
                    <BranchSelect className="w-full" />
                  </div>
                  <button
                    type="button"
                    onClick={() => { setUserMenuOpen(false); logout() }}
                    className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[#202223] hover:bg-[#f6f6f7]"
                  >
                    <LogOut size={16} />
                    Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        </header>

        {/* Mobile nav */}
        <nav className="flex shrink-0 gap-1 overflow-x-auto border-b border-[#e1e3e5] bg-white px-2 py-2 md:hidden">
          {navItems.slice(0, 6).map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${
                    isActive ? 'bg-[#008060] text-white' : 'text-[#6d7175] bg-[#f6f6f7]'
                  }`
                }
              >
                <Icon size={14} />
                {item.label.split(' ')[0]}
              </NavLink>
            )
          })}
        </nav>

        <main className="flex-1 overflow-hidden flex flex-col min-h-0">
          {children}
        </main>
      </div>
    </div>
  )
}
