import { useEffect, useState } from 'react'
import { getBranches, getOrders, getProducts, getCustomers, getExpenses } from '../api/api'

const statConfig = [
  { key: 'orders', label: 'Total Orders', color: 'bg-indigo-500' },
  { key: 'products', label: 'Total Products', color: 'bg-emerald-500' },
  { key: 'customers', label: 'Total Customers', color: 'bg-orange-500' },
  { key: 'expenses', label: 'Total Expenses', color: 'bg-rose-500' },
]

export default function Dashboard() {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [stats, setStats] = useState({ orders: 0, products: 0, customers: 0, expenses: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getBranches().then(res => {
      setBranches(res.data)
      if (res.data.length > 0) setSelectedBranch(res.data[0])
    })
  }, [])

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
          orders: orders.data.length,
          products: products.data.length,
          customers: customers.data.length,
          expenses: expenses.data.length,
        })
      })
      .catch(() => {
        // fallback if API fails
        setStats({ orders: 0, products: 0, customers: 0, expenses: 0 })
      })
      .finally(() => setLoading(false))
  }, [selectedBranch])

  const isEmpty = !loading && Object.values(stats).every(v => v === 0)

  return (
    <div className="space-y-8 text-gray-800">

      {/* Header */}
      <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-gray-500 mt-1">
            Overview for <span className="font-medium">{selectedBranch?.name || '...'}</span>
          </p>
        </div>

        {/* Branch Selector */}
        <select
          className="border border-gray-300 rounded-lg px-4 py-2 bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          onChange={(e) => {
            const branch = branches.find(b => b.id === Number(e.target.value))
            setSelectedBranch(branch)
          }}
          value={selectedBranch?.id || ''}
        >
          {branches.map(branch => (
            <option key={branch.id} value={branch.id}>
              {branch.name} — {branch.city}
            </option>
          ))}
        </select>
      </div>

      {/* Stats */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map(i => (
            <div
              key={i}
              className="h-28 bg-gray-200/70 animate-pulse rounded-2xl"
            />
          ))}
        </div>
      ) : isEmpty ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg font-medium">No data available</p>
          <p className="text-sm mt-2">This branch has no activity yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {statConfig.map(s => (
            <div
              key={s.key}
              className="relative overflow-hidden rounded-2xl bg-white shadow-md p-5 border hover:shadow-lg transition"
            >
              <div className={`absolute top-0 left-0 w-1 h-full ${s.color}`} />

              <p className="text-sm text-gray-500">{s.label}</p>
              <p className="text-3xl font-bold mt-2">{stats[s.key]}</p>
            </div>
          ))}
        </div>
      )}

      {/* Branch Info */}
      {selectedBranch && (
        <div className="bg-white p-6 rounded-2xl shadow-md border">
          <h2 className="text-lg font-semibold mb-6">Branch Information</h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { label: 'Name', value: selectedBranch.name },
              { label: 'City', value: selectedBranch.city },
              { label: 'Address', value: selectedBranch.address },
              { label: 'Phone', value: selectedBranch.phone },
              { label: 'Email', value: selectedBranch.email },
              {
                label: 'Status',
                value: selectedBranch.is_active ? 'Active' : 'Inactive',
              },
            ].map(item => (
              <div key={item.label}>
                <p className="text-sm text-gray-500">{item.label}</p>
                <p className="font-semibold text-gray-800 mt-1">
                  {item.value || '—'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  )
}