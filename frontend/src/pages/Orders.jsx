import { useEffect, useState, useMemo } from 'react'
import { getOrders, getBranches, updateOrder, deleteOrder } from '../api/api'

const STATUS_FLOW = ['pending', 'confirmed', 'in_progress', 'ready', 'completed', 'cancelled']

const statusStyle = {
  pending:     'bg-yellow-50 text-yellow-700 border-yellow-200',
  confirmed:   'bg-blue-50 text-blue-700 border-blue-200',
  in_progress: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  ready:       'bg-purple-50 text-purple-700 border-purple-200',
  completed:   'bg-emerald-50 text-emerald-700 border-emerald-200',
  cancelled:   'bg-rose-50 text-rose-700 border-rose-200',
}

const paymentStyle = {
  unpaid:  'bg-rose-50 text-rose-700',
  deposit: 'bg-yellow-50 text-yellow-700',
  partial: 'bg-amber-50 text-amber-700',
  paid:    'bg-emerald-50 text-emerald-700',
}

const statusLabel = {
  pending: 'Pending', confirmed: 'Confirmed', in_progress: 'In Progress',
  ready: 'Ready', completed: 'Completed', cancelled: 'Cancelled',
}

export default function Orders() {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('quick_sale')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState(null)
  const [editingOrder, setEditingOrder] = useState(null)
  const [editForm, setEditForm] = useState({})

  const toNum = (v) => Number(v) || 0

  useEffect(() => {
    getBranches().then(r => {
      setBranches(r.data)
      if (r.data.length > 0) setSelectedBranch(r.data[0])
    })
  }, [])

  useEffect(() => {
    if (!selectedBranch) return
    setLoading(true)
    getOrders(selectedBranch.id)
      .then(r => setOrders(r.data))
      .finally(() => setLoading(false))
  }, [selectedBranch])

  const filtered = useMemo(() => {
    return orders
      .filter(o => o.transaction_type === tab)
      .filter(o =>
        o.order_number?.toLowerCase().includes(search.toLowerCase()) ||
        o.payment_status?.toLowerCase().includes(search.toLowerCase()) ||
        o.status?.toLowerCase().includes(search.toLowerCase())
      )
  }, [orders, tab, search])

  const quickStats = useMemo(() => {
    const tabOrders = orders.filter(o => o.transaction_type === tab)
    return {
      total: tabOrders.length,
      pending: tabOrders.filter(o => ['pending', 'confirmed', 'in_progress', 'ready'].includes(o.status)).length,
      completed: tabOrders.filter(o => o.status === 'completed').length,
      unpaid: tabOrders.filter(o => o.payment_status !== 'paid').length,
    }
  }, [orders, tab])

  const openEdit = (order) => {
    setEditingOrder(order)
    setEditForm({
      status: order.status,
      payment_status: order.payment_status,
      payment_method: order.payment_method,
      amount_paid: order.amount_paid,
      notes: order.notes || '',
      estimated_completion: order.estimated_completion || '',
    })
  }

  const handleUpdate = async () => {
    try {
      const res = await updateOrder(editingOrder.id, {
        ...editingOrder,
        ...editForm,
        amount_paid: toNum(editForm.amount_paid),
      })
      setOrders(prev => prev.map(o => o.id === res.data.id ? res.data : o))
      setEditingOrder(null)
    } catch (err) {
      alert('Update failed: ' + JSON.stringify(err.response?.data))
    }
  }

  const handleStatusStep = async (order, direction) => {
    const idx = STATUS_FLOW.indexOf(order.status)
    const next = STATUS_FLOW[idx + direction]
    if (!next || next === 'cancelled') return
    try {
      const res = await updateOrder(order.id, { ...order, status: next })
      setOrders(prev => prev.map(o => o.id === res.data.id ? res.data : o))
    } catch {
      alert('Could not update status')
    }
  }

  const handleCancel = async (order) => {
    if (!confirm(`Cancel order ${order.order_number}?`)) return
    try {
      const res = await updateOrder(order.id, { ...order, status: 'cancelled' })
      setOrders(prev => prev.map(o => o.id === res.data.id ? res.data : o))
    } catch {
      alert('Could not cancel order')
    }
  }

  const handleDelete = async (order) => {
    if (!confirm(`Permanently delete order ${order.order_number}? This cannot be undone.`)) return
    try {
      await deleteOrder(order.id)
      setOrders(prev => prev.filter(o => o.id !== order.id))
    } catch {
      alert('Delete failed')
    }
  }
    return (
    <div className="p-8">

      {/* header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Orders</h1>
          <p className="text-sm text-gray-400 mt-0.5">Manage all sales and custom orders</p>
        </div>
        <select value={selectedBranch?.id || ''}
          onChange={e => setSelectedBranch(branches.find(b => b.id === parseInt(e.target.value)))}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300">
          {branches.map(b => <option key={b.id} value={b.id}>{b.name} — {b.city}</option>)}
        </select>
      </div>

      {/* stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total', value: quickStats.total, color: 'text-gray-800' },
          { label: 'Active', value: quickStats.pending, color: 'text-indigo-600' },
          { label: 'Completed', value: quickStats.completed, color: 'text-emerald-600' },
          { label: 'Unpaid', value: quickStats.unpaid, color: 'text-rose-600' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-100 px-5 py-4">
            <p className="text-xs text-gray-400 mb-1">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* tabs + search */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {[{ k: 'quick_sale', l: 'Quick Sales' }, { k: 'custom_order', l: 'Custom Orders' }].map(t => (
            <button key={t.k} onClick={() => setTab(t.k)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition ${tab === t.k ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
              {t.l}
            </button>
          ))}
        </div>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search order number, status..."
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-indigo-300" />
      </div>

      {/* orders table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading orders...</div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">No {tab === 'quick_sale' ? 'quick sales' : 'custom orders'} found.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-5 py-3 text-left">Order</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-5 py-3 text-left">Payment</th>
                <th className="px-5 py-3 text-left">Total</th>
                <th className="px-5 py-3 text-left">Balance</th>
                <th className="px-5 py-3 text-left">Date</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map(order => (
                <>
                  <tr key={order.id} className="hover:bg-gray-50 transition">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <button onClick={() => setExpanded(expanded === order.id ? null : order.id)}
                          className="w-5 h-5 rounded bg-gray-100 text-gray-500 text-xs flex items-center justify-center hover:bg-gray-200 transition">
                          {expanded === order.id ? '−' : '+'}
                        </button>
                        <div>
                          <p className="font-medium text-gray-800">{order.order_number}</p>
                          <p className="text-xs text-gray-400">{order.payment_method || 'No method'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1">
                        {order.status !== 'cancelled' && order.status !== 'pending' && (
                          <button onClick={() => handleStatusStep(order, -1)}
                            className="text-gray-300 hover:text-gray-500 text-xs">◀</button>
                        )}
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusStyle[order.status] || ''}`}>
                          {statusLabel[order.status] || order.status}
                        </span>
                        {order.status !== 'cancelled' && order.status !== 'completed' && (
                          <button onClick={() => handleStatusStep(order, 1)}
                            className="text-gray-300 hover:text-gray-500 text-xs">▶</button>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${paymentStyle[order.payment_status] || ''}`}>
                        {order.payment_status}
                      </span>
                    </td>
                    <td className="px-5 py-3 font-medium text-gray-800">${toNum(order.total_amount).toFixed(2)}</td>
                    <td className={`px-5 py-3 font-medium ${toNum(order.balance_due) > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                      ${toNum(order.balance_due).toFixed(2)}
                    </td>
                    <td className="px-5 py-3 text-gray-400 text-xs">
                      {new Date(order.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => openEdit(order)}
                          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium">Edit</button>
                        {order.status !== 'cancelled' && order.status !== 'completed' && (
                          <button onClick={() => handleCancel(order)}
                            className="text-xs text-amber-600 hover:text-amber-800 font-medium">Cancel</button>
                        )}
                        <button onClick={() => handleDelete(order)}
                          className="text-xs text-rose-500 hover:text-rose-700 font-medium">Delete</button>
                      </div>
                    </td>
                  </tr>

                  {/* expanded order items */}
                  {expanded === order.id && (
                    <tr key={order.id + '-items'}>
                      <td colSpan="7" className="px-5 py-3 bg-gray-50 border-t border-gray-100">
                        <div className="grid grid-cols-2 gap-6">
                          <div>
                            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Order items</p>
                            {order.items?.length ? (
                              <div className="space-y-1.5">
                                {order.items.map((item, i) => (
                                  <div key={i} className="flex justify-between items-start text-xs bg-white rounded-lg px-3 py-2 border border-gray-100">
                                    <div>
                                      <p className="font-medium text-gray-700">{item.product_name || 'Product'}</p>
                                      {item.customization_details && (
                                        <p className="text-purple-600 mt-0.5">✦ {item.customization_details}</p>
                                      )}
                                    </div>
                                    <div className="text-right">
                                      <p className="font-medium">x{item.quantity}</p>
                                      <p className="text-gray-400">${toNum(item.subtotal).toFixed(2)}</p>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : <p className="text-xs text-gray-400">No items recorded</p>}
                          </div>
                          <div>
                            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Order details</p>
                            <div className="bg-white rounded-lg px-3 py-2 border border-gray-100 text-xs space-y-1.5">
                              {order.discount_amount > 0 && (
                                <div className="flex justify-between">
                                  <span className="text-gray-400">Discount</span>
                                  <span className="text-emerald-600">-${toNum(order.discount_amount).toFixed(2)} {order.discount_reason && `(${order.discount_reason})`}</span>
                                </div>
                              )}
                              <div className="flex justify-between"><span className="text-gray-400">Amount paid</span><span>${toNum(order.amount_paid).toFixed(2)}</span></div>
                              {order.notes && <div className="flex justify-between"><span className="text-gray-400">Notes</span><span className="text-right max-w-40">{order.notes}</span></div>}
                              {order.estimated_completion && <div className="flex justify-between"><span className="text-gray-400">Due date</span><span className="text-purple-600">{order.estimated_completion}</span></div>}
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* edit modal */}
      {editingOrder && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Edit order {editingOrder.order_number}</h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Status</label>
                <select value={editForm.status} onChange={e => setEditForm({...editForm, status: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                  {STATUS_FLOW.map(s => <option key={s} value={s}>{statusLabel[s]}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Payment status</label>
                <select value={editForm.payment_status} onChange={e => setEditForm({...editForm, payment_status: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                  <option value="unpaid">Unpaid</option>
                  <option value="deposit">Deposit paid</option>
                  <option value="partial">Partially paid</option>
                  <option value="paid">Fully paid</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Payment method</label>
                <select value={editForm.payment_method} onChange={e => setEditForm({...editForm, payment_method: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                  <option value="cash">Cash</option>
                  <option value="card">Card</option>
                  <option value="mobile_money">Mobile Money</option>
                  <option value="bank_transfer">Bank Transfer</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Amount paid ($)</label>
                <input type="number" value={editForm.amount_paid}
                  onChange={e => setEditForm({...editForm, amount_paid: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
              </div>
              {editingOrder.transaction_type === 'custom_order' && (
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Estimated completion</label>
                  <input type="date" value={editForm.estimated_completion}
                    onChange={e => setEditForm({...editForm, estimated_completion: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
              )}
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Notes</label>
                <textarea rows={2} value={editForm.notes}
                  onChange={e => setEditForm({...editForm, notes: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none" />
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={handleUpdate}
                className="flex-1 bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700 transition">
                Save changes
              </button>
              <button onClick={() => setEditingOrder(null)}
                className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm hover:bg-gray-50 transition">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}