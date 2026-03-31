import { useEffect, useState } from 'react'
import { getBranches, getOrders, getProducts, getCustomers, getExpenses } from '../api/api'

const statConfig = [
  { key: 'orders', label: 'Total Orders', color: 'bg-indigo-50 text-indigo-700' },
  { key: 'products', label: 'Total Products', color: 'bg-emerald-50 text-emerald-700' },
  { key: 'customers', label: 'Total Customers', color: 'bg-orange-50 text-orange-700' },
  { key: 'expenses', label: 'Total Expenses', color: 'bg-rose-50 text-rose-700' },
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
    ]).then(([orders, products, customers, expenses]) => {
      setStats({
        orders: orders.data.length,
        products: products.data.length,
        customers: customers.data.length,
        expenses: expenses.data.length,
      })
      setLoading(false)
    })
  }, [selectedBranch])

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-gray-500">Welcome back. Here is what is happening today.</p>
        </div>

        {/* Branch Selector */}
        <select
          className="border rounded-lg px-3 py-2"
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
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-24 bg-gray-200 animate-pulse rounded-xl"></div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-4">
          {statConfig.map(s => (
            <div key={s.key} className={`p-4 rounded-xl shadow-sm ${s.color}`}>
              <p className="text-sm">{s.label}</p>
              <p className="text-2xl font-bold">{stats[s.key]}</p>
            </div>
          ))}
        </div>
      )}

      {/* Branch Info */}
      {selectedBranch && (
        <div className="bg-white p-6 rounded-xl shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Branch Info</h2>

          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'Name', value: selectedBranch.name },
              { label: 'City', value: selectedBranch.city },
              { label: 'Address', value: selectedBranch.address },
              { label: 'Phone', value: selectedBranch.phone },
              { label: 'Email', value: selectedBranch.email },
              { label: 'Status', value: selectedBranch.is_active ? 'Active' : 'Inactive' },
            ].map(item => (
              <div key={item.label}>
                <p className="text-sm text-gray-500">{item.label}</p>
                <p className="font-medium">{item.value || '—'}</p>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  )
}