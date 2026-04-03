import { useEffect, useState } from 'react'
import { getOrders, createOrder } from '../api/api'
import { useBranch } from '../context/BranchContext'

const statusColors = {
  pending: 'bg-yellow-50 text-yellow-700',
  confirmed: 'bg-blue-50 text-blue-700',
  in_progress: 'bg-indigo-50 text-indigo-700',
  ready: 'bg-purple-50 text-purple-700',
  completed: 'bg-emerald-50 text-emerald-700',
  cancelled: 'bg-rose-50 text-rose-700',
}

const paymentColors = {
  unpaid: 'bg-rose-50 text-rose-700',
  partial: 'bg-yellow-50 text-yellow-700',
  paid: 'bg-emerald-50 text-emerald-700',
}

export default function Orders() {
  const { selectedBranch } = useBranch()

  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)

  const [form, setForm] = useState({
    order_number: '',
    payment_method: 'cash',
    notes: '',
    total_amount: '',
    amount_paid: 0,
  })

  // ✅ Load orders when branch changes
  useEffect(() => {
    if (!selectedBranch) return

    setLoading(true)

    getOrders(selectedBranch.id)
      .then(res => {
        const data = Array.isArray(res.data)
          ? res.data
          : res.data?.results || []
        setOrders(data)
      })
      .catch(err => {
        console.error('Failed to fetch orders:', err)
        setOrders([])
      })
      .finally(() => setLoading(false))
  }, [selectedBranch])

  const handleSubmit = (e) => {
    e.preventDefault()

    const payload = {
      ...form,
      branch: selectedBranch?.id,
    }

    createOrder(payload)
      .then(res => {
        setOrders(prev => [...prev, res.data])
        setShowForm(false)

        setForm({
          order_number: '',
          payment_method: 'cash',
          notes: '',
          total_amount: '',
          amount_paid: 0,
        })
      })
      .catch(err => {
        console.error(err.response?.data)
        alert('Failed to save order')
      })
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Orders</h1>
          <p className="text-gray-500">
            Branch: {selectedBranch?.name || 'Select branch'}
          </p>
        </div>

        <button
          onClick={() => setShowForm(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700"
        >
          + New Order
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="bg-white p-4 rounded-xl border">
          <h2 className="font-semibold mb-4">New Order</h2>

          <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">

            <input
              placeholder="Order number"
              value={form.order_number}
              onChange={e => setForm({ ...form, order_number: e.target.value })}
              className="border p-2 rounded"
              required
            />

            <select
              value={form.payment_method}
              onChange={e => setForm({ ...form, payment_method: e.target.value })}
              className="border p-2 rounded"
            >
              <option value="cash">Cash</option>
              <option value="card">Card</option>
              <option value="transfer">Transfer</option>
            </select>

            <input
              type="number"
              placeholder="Total amount"
              value={form.total_amount}
              onChange={e => setForm({ ...form, total_amount: e.target.value })}
              className="border p-2 rounded"
              required
            />

            <input
              type="number"
              placeholder="Amount paid"
              value={form.amount_paid}
              onChange={e => setForm({ ...form, amount_paid: e.target.value })}
              className="border p-2 rounded"
            />

            <textarea
              placeholder="Notes"
              value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })}
              className="border p-2 rounded md:col-span-2"
            />

            <div className="flex justify-end gap-2 md:col-span-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="border px-3 py-1 rounded"
              >
                Cancel
              </button>

              <button className="bg-indigo-600 text-white px-3 py-1 rounded">
                Save
              </button>
            </div>

          </form>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border overflow-hidden">
        {loading ? (
          <div className="p-6 text-center text-gray-400">Loading...</div>
        ) : orders.length === 0 ? (
          <div className="p-6 text-center text-gray-400">No orders</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="p-3 text-left">Order</th>
                <th className="p-3 text-left">Status</th>
                <th className="p-3 text-left">Payment</th>
                <th className="p-3 text-left">Total</th>
                <th className="p-3 text-left">Paid</th>
                <th className="p-3 text-left">Balance</th>
              </tr>
            </thead>

            <tbody>
              {orders.map(o => (
                <tr key={o.id} className="border-t">
                  <td className="p-3">{o.order_number}</td>

                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs ${statusColors[o.status]}`}>
                      {o.status}
                    </span>
                  </td>

                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs ${paymentColors[o.payment_status]}`}>
                      {o.payment_status}
                    </span>
                  </td>

                  <td className="p-3">${o.total_amount}</td>
                  <td className="p-3">${o.amount_paid}</td>
                  <td className="p-3 text-rose-600">${o.balance_due}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

    </div>
  )
}