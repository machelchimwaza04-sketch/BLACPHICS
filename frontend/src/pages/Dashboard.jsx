import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ShoppingCart, Box, Users, Wallet, CreditCard, ArrowRight,
  MapPin, Phone, Mail,
} from 'lucide-react'
import { getOrders, getProducts, getCustomers, getExpenses } from '../api/api'
import { useBranch } from '../context/BranchContext'
import PageHeader from '../components/ui/PageHeader'
import StatCard from '../components/ui/StatCard'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import { formatNumber } from '../lib/format'

const statConfig = [
  { key: 'orders', label: 'Orders', icon: ShoppingCart, accent: 'brand' },
  { key: 'products', label: 'Products', icon: Box, accent: 'blue' },
  { key: 'customers', label: 'Customers', icon: Users, accent: 'amber' },
  { key: 'expenses', label: 'Expenses', icon: Wallet, accent: 'rose' },
]

const quickActions = [
  { to: '/pos', label: 'New sale', desc: 'Open point of sale', icon: CreditCard },
  { to: '/products', label: 'Manage products', desc: 'Inventory & variants', icon: Box },
  { to: '/orders', label: 'View orders', desc: 'Track fulfillment', icon: ShoppingCart },
]

export default function Dashboard() {
  const { selectedBranch } = useBranch()
  const [stats, setStats] = useState({ orders: 0, products: 0, customers: 0, expenses: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!selectedBranch) return
    setLoading(true)
    Promise.all([
      getOrders(selectedBranch.id),
      getProducts(selectedBranch.id),
      getCustomers(selectedBranch.id),
      getExpenses(selectedBranch.id),
    ])
      .then(([orders, products, customers, expenses]) => {
        setStats({
          orders: (Array.isArray(orders.data) ? orders.data : orders.data?.results || []).length,
          products: (Array.isArray(products.data) ? products.data : products.data?.results || []).length,
          customers: (Array.isArray(customers.data) ? customers.data : customers.data?.results || []).length,
          expenses: (Array.isArray(expenses.data) ? expenses.data : expenses.data?.results || []).length,
        })
      })
      .catch(() => setStats({ orders: 0, products: 0, customers: 0, expenses: 0 }))
      .finally(() => setLoading(false))
  }, [selectedBranch])

  const isEmpty = !loading && Object.values(stats).every((v) => v === 0)

  return (
    <div>
      <PageHeader
        title={`Good day${selectedBranch ? `, ${selectedBranch.name}` : ''}`}
        description="Here's what's happening in your store today."
        actions={
          <Link to="/pos">
            <Button>
              <CreditCard size={16} />
              New sale
            </Button>
          </Link>
        }
      />

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-[#e1e3e5]/60" />
          ))}
        </div>
      ) : isEmpty ? (
        <EmptyState
          icon={ShoppingCart}
          title="Your store is ready to go"
          description="Add products and create your first sale to see metrics here."
          action={
            <Link to="/pos">
              <Button>Create first sale</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {statConfig.map((s) => (
            <StatCard
              key={s.key}
              label={s.label}
              value={formatNumber(stats[s.key])}
              icon={s.icon}
              accent={s.accent}
            />
          ))}
        </div>
      )}

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="text-base font-semibold text-[#202223]">Quick actions</h2>
          <p className="mt-0.5 text-sm text-[#6d7175]">Jump to common tasks</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {quickActions.map((action) => {
              const Icon = action.icon
              return (
                <Link
                  key={action.to}
                  to={action.to}
                  className="group flex flex-col rounded-lg border border-[#e1e3e5] p-4 transition hover:border-[#008060]/40 hover:bg-[#f0fdf4]/50"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#008060]/10 text-[#008060]">
                    <Icon size={18} />
                  </div>
                  <p className="mt-3 text-sm font-semibold text-[#202223] group-hover:text-[#008060]">
                    {action.label}
                  </p>
                  <p className="mt-0.5 text-xs text-[#6d7175]">{action.desc}</p>
                  <ArrowRight size={14} className="mt-2 text-[#6d7175] opacity-0 transition group-hover:opacity-100" />
                </Link>
              )
            })}
          </div>
        </Card>

        {selectedBranch && (
          <Card>
            <h2 className="text-base font-semibold text-[#202223]">Store details</h2>
            <ul className="mt-4 space-y-3 text-sm">
              {[
                { icon: MapPin, label: 'Location', value: [selectedBranch.city, selectedBranch.address].filter(Boolean).join(' · ') },
                { icon: Phone, label: 'Phone', value: selectedBranch.phone },
                { icon: Mail, label: 'Email', value: selectedBranch.email },
              ].map((row) => {
                const Icon = row.icon
                return (
                  <li key={row.label} className="flex gap-3">
                    <Icon size={16} className="mt-0.5 shrink-0 text-[#6d7175]" />
                    <div>
                      <p className="text-xs text-[#6d7175]">{row.label}</p>
                      <p className="font-medium text-[#202223]">{row.value || '—'}</p>
                    </div>
                  </li>
                )
              })}
            </ul>
          </Card>
        )}
      </div>
    </div>
  )
}
