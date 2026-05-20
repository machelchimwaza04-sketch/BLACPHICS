import { useEffect, useState, useMemo } from 'react'
import React from 'react'
import { getOrders, getBranches, updateOrder, deleteOrder, addPayment } from '../api/api'

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

const PAYMENT_METHODS = [
  { key: 'cash', label: 'Cash' },
  { key: 'card', label: 'Card' },
  { key: 'mobile_money', label: 'Mobile Money' },
  { key: 'bank_transfer', label: 'Bank Transfer' },
]

export default function Orders() {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [orders, setOrders] = useState([])
  const [orderDetails, setOrderDetails] = useState({})
  const [loadingOrderDetails, setLoadingOrderDetails] = useState({})
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('quick_sale')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState(null)
  const [editingOrder, setEditingOrder] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [paymentModal, setPaymentModal] = useState(null)
  const [paymentForm, setPaymentForm] = useState({ amount: '', method: 'cash' })
  const [paymentLoading, setPaymentLoading] = useState(false)

  const PAYMENT_METHOD_CONFIG = {
    cash: { icon: '💵', label: 'Cash', color: 'text-emerald-600' },
    card: { icon: '💳', label: 'Card', color: 'text-blue-600' },
    mobile_money: { icon: '📱', label: 'Mobile', color: 'text-purple-600' },
    bank_transfer: { icon: '🏦', label: 'Bank', color: 'text-indigo-600' },
  }

  const toNum = (v) => Number(v) || 0
  const formatCurrency = (value) => `$${toNum(value).toFixed(2)}`

  const getOrderAgeLabel = (order) => {
    const minutesOld = Math.floor((Date.now() - new Date(order.created_at)) / 60000)
    if (order.payment_status === 'paid') return null
    if (minutesOld >= 60) return `${Math.floor(minutesOld / 60)}h ago`
    if (minutesOld >= 30) return `${minutesOld}m ago`
    return null
  }

  useEffect(() => {
    getBranches().then(r => {
      setBranches(r.data)
      if (r.data.length > 0) setSelectedBranch(r.data[0])
    })
  }, [])

  useEffect(() => {
    if (!selectedBranch || !selectedBranch.id) return
    setLoading(true)

    const params = {}
    if (tab === 'completed') {
      params.payment_status = 'paid'
      params.status = 'completed'
    } else {
      params.transaction_type = tab
    }

    getOrders(selectedBranch.id, params)
      .then(r => {
        setOrders(Array.isArray(r.data) ? r.data : [])
      })
      .catch(err => {
        console.error('Failed to load orders:', err.response?.data || err.message)
        setOrders([])
      })
      .finally(() => setLoading(false))
  }, [selectedBranch, tab])

  const filtered = useMemo(() => {
    return orders.filter(o =>
      o.order_number?.toLowerCase().includes(search.toLowerCase()) ||
      o.payment_status?.toLowerCase().includes(search.toLowerCase()) ||
      o.status?.toLowerCase().includes(search.toLowerCase())
    )
  }, [orders, search])

  const quickStats = useMemo(() => ({
    total: orders.length,
    pending: orders.filter(o => ['pending', 'confirmed', 'in_progress', 'ready'].includes(o.status)).length,
    completed: orders.filter(o => o.status === 'completed').length,
    unpaid: orders.filter(o => o.payment_status !== 'paid').length,
  }), [orders])

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
        status: editForm.status,
        payment_status: editForm.payment_status,
        payment_method: editForm.payment_method,
        amount_paid: toNum(editForm.amount_paid),
        notes: editForm.notes,
        estimated_completion: editForm.estimated_completion || null,
      })
      setOrders(prev => prev.map(o => o.id === res.data.id ? res.data : o))
      setOrderDetails(prev => prev[res.data.id] ? { ...prev, [res.data.id]: res.data } : prev)
      setEditingOrder(null)
    } catch (err) {
      alert('Update failed: ' + JSON.stringify(err.response?.data))
    }
  }

  const openPaymentModal = (order) => {
    setPaymentModal(order)
    setPaymentForm({ amount: '', method: 'cash' })
  }

  const handleToggleExpand = async (order) => {
    if (expanded === order.id) {
      setExpanded(null)
      return
    }

    setExpanded(order.id)
    if (orderDetails[order.id]) {
      return
    }

    setLoadingOrderDetails(prev => ({ ...prev, [order.id]: true }))
    try {
      console.log(`Fetching order details for order ${order.id}...`)
      const res = await getOrder(order.id)
      console.log(`Order detail response:`, res)
      const orderData = res.data || res
      setOrderDetails(prev => ({ ...prev, [order.id]: orderData }))
    } catch (err) {
      console.error(`Failed to load order ${order.id}:`, err)
      console.error('Error response:', err.response?.data, err.response?.status)
      // Fallback: use cached list data
      setOrderDetails(prev => ({ ...prev, [order.id]: order }))
    } finally {
      setLoadingOrderDetails(prev => ({ ...prev, [order.id]: false }))
    }
  }

  const handleAddPayment = async () => {
    if (!paymentForm.amount || toNum(paymentForm.amount) <= 0) {
      alert('Please enter a valid amount')
      return
    }

    if (toNum(paymentForm.amount) > toNum(paymentModal.balance_due)) {
      alert(`Payment exceeds balance of $${toNum(paymentModal.balance_due).toFixed(2)}`)
      return
    }

    setPaymentLoading(true)
    try {
      const res = await addPayment(paymentModal.id, {
        amount: toNum(paymentForm.amount),
        method: paymentForm.method,
        payment_type: 'payment',
        notes: `Payment received via ${paymentForm.method}`
      })
      setOrders(prev => prev.map(o => o.id === res.data.id ? res.data : o))
      setOrderDetails(prev => prev[res.data.id] ? { ...prev, [res.data.id]: res.data } : prev)
      setPaymentModal(null)
      setPaymentForm({ amount: '', method: 'cash' })
    } catch (err) {
      alert('Payment failed: ' + (err.response?.data?.error || JSON.stringify(err.response?.data)))
    } finally {
      setPaymentLoading(false)
    }
  }

  const handlePayFull = async (order) => {
    const amount = toNum(order.balance_due)
    if (amount <= 0) return
    setPaymentLoading(true)
    try {
      const res = await addPayment(order.id, {
        amount,
        method: order.payment_method || 'cash',
        payment_type: 'payment',
        notes: `Quick pay full balance`
      })
      setOrders(prev => prev.map(o => o.id === res.data.id ? res.data : o))
      setOrderDetails(prev => prev[res.data.id] ? { ...prev, [res.data.id]: res.data } : prev)
    } catch (err) {
      alert('Quick payment failed: ' + (err.response?.data?.error || JSON.stringify(err.response?.data)))
    } finally {
      setPaymentLoading(false)
    }
  }

  const handleStatusStep = async (order, direction) => {
    const idx = STATUS_FLOW.indexOf(order.status)
    const next = STATUS_FLOW[idx + direction]
    if (!next || next === 'cancelled') return
    try {
      const res = await updateOrder(order.id, { status: next })
      setOrders(prev => prev.map(o => o.id === res.data.id ? res.data : o))
      setOrderDetails(prev => prev[res.data.id] ? { ...prev, [res.data.id]: res.data } : prev)
    } catch {
      alert('Could not update status')
    }
  }

  const handleCancel = async (order) => {
    if (!confirm(`Cancel order ${order.order_number}?`)) return
    try {
      const res = await updateOrder(order.id, { status: 'cancelled' })
      setOrders(prev => prev.map(o => o.id === res.data.id ? res.data : o))
      setOrderDetails(prev => prev[res.data.id] ? { ...prev, [res.data.id]: res.data } : prev)
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
          {[
            { k: 'quick_sale', l: 'Quick Sales' }, 
            { k: 'custom_order', l: 'Custom Orders' },
            { k: 'completed', l: 'Completed Sales' }
          ].map(t => (
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
          <div className="p-8 text-center text-gray-400 text-sm">
            {tab === 'quick_sale' ? 'No quick sales found.' : tab === 'custom_order' ? 'No custom orders found.' : 'No completed sales found.'}
          </div>
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
                <React.Fragment key={order.id}>
                  <tr className="hover:bg-gray-50 transition">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <button onClick={() => handleToggleExpand(order)}
                            className="w-5 h-5 rounded bg-gray-100 text-gray-500 text-xs flex items-center justify-center hover:bg-gray-200 transition">
                            {expanded === order.id ? '−' : '+'}
                          </button>
                          <div>
                            <p className="font-medium text-gray-800">{order.order_number}</p>
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              {order.customer_name ? (
                                <span className="text-indigo-500 font-medium">{order.customer_name}</span>
                              ) : (
                                <span className="text-gray-400">Walk-in</span>
                              )}
                              {order.payment_method && PAYMENT_METHOD_CONFIG[order.payment_method] && (
                                <span className={`text-xs ${PAYMENT_METHOD_CONFIG[order.payment_method].color}`}>
                                  {PAYMENT_METHOD_CONFIG[order.payment_method].icon} {PAYMENT_METHOD_CONFIG[order.payment_method].label}
                                </span>
                              )}
                              {getOrderAgeLabel(order) && (
                                <span className="text-gray-500">{getOrderAgeLabel(order)}</span>
                              )}
                            </div>
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
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${paymentStyle[order.payment_status] || ''}`}>
                            {order.payment_status}
                          </span>
                          {toNum(order.balance_due) > 0 && (
                            <button onClick={() => handlePayFull(order)}
                              className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full hover:bg-emerald-100 transition">
                              Pay full
                            </button>
                          )}
                        </div>
                        <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${order.payment_status === 'paid' ? 'bg-emerald-500' : order.payment_status === 'partial' ? 'bg-yellow-400' : 'bg-rose-400'}`}
                            style={{ width: `${Math.min((toNum(order.amount_paid) / Math.max(toNum(order.total_amount), 1)) * 100, 100)}%` }}
                          />
                        </div>
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>{formatCurrency(order.amount_paid)} paid</span>
                          <span>{formatCurrency(order.balance_due)} due</span>
                        </div>
                      </div>
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
                        {toNum(order.balance_due) > 0 && (
                          <button onClick={() => openPaymentModal(order)}
                            className="text-xs text-emerald-600 hover:text-emerald-800 font-medium">Update Payment</button>
                        )}
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
                        {loadingOrderDetails[order.id] ? (
                          <div className="text-sm text-gray-500">Loading order details...</div>
                        ) : !orderDetails[order.id] ? (
                          <div className="text-sm text-gray-500">Unable to load details. Try again.</div>
                        ) : (
                          <div className="grid grid-cols-2 gap-6">
                            <div>
                              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Order items</p>
                              {orderDetails[order.id].items?.length ? (
                                <div className="space-y-1.5">
                                  {orderDetails[order.id].items.map((item, i) => (
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
                                {orderDetails[order.id].discount_amount > 0 && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-400">Discount</span>
                                    <span className="text-emerald-600">-${toNum(orderDetails[order.id].discount_amount).toFixed(2)} {orderDetails[order.id].discount_reason && `(${orderDetails[order.id].discount_reason})`}</span>
                                  </div>
                                )}
                                <div className="flex justify-between"><span className="text-gray-400">Amount paid</span><span>${toNum(orderDetails[order.id].amount_paid).toFixed(2)}</span></div>
                                {orderDetails[order.id].notes && <div className="flex justify-between"><span className="text-gray-400">Notes</span><span className="text-right max-w-40">{orderDetails[order.id].notes}</span></div>}
                                {orderDetails[order.id].estimated_completion && <div className="flex justify-between"><span className="text-gray-400">Due date</span><span className="text-purple-600">{orderDetails[order.id].estimated_completion}</span></div>}
                              </div>
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
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

      {/* payment modal */}
      {paymentModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Record Payment</h2>
            <p className="text-sm text-gray-600 mb-4">Order: <span className="font-medium">{paymentModal.order_number}</span></p>
            
            {/* summary */}
            <div className="bg-gray-50 rounded-lg p-3 mb-4 space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Original Total:</span>
                <span className="font-medium text-gray-800">${toNum(paymentModal.total_amount).toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Total Paid to Date:</span>
                <span className="font-medium text-emerald-600">${toNum(paymentModal.amount_paid).toFixed(2)}</span>
              </div>
              <div className="flex justify-between border-t border-gray-200 pt-1.5">
                <span className="text-gray-600">Current Balance:</span>
                <span className="font-semibold text-rose-600">${toNum(paymentModal.balance_due).toFixed(2)}</span>
              </div>
            </div>

            {/* form */}
            <div className="space-y-3 mb-5">
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Amount to Pay ($)</label>
                <input 
                  type="number" 
                  step="0.01"
                  value={paymentForm.amount}
                  onChange={e => setPaymentForm({...paymentForm, amount: e.target.value})}
                  placeholder={`Max: $${toNum(paymentModal.balance_due).toFixed(2)}`}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Payment Method</label>
                <select 
                  value={paymentForm.method} 
                  onChange={e => setPaymentForm({...paymentForm, method: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                  {PAYMENT_METHODS.map(m => (
                    <option key={m.key} value={m.key}>{m.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* actions */}
            <div className="flex gap-3">
              <button 
                onClick={handleAddPayment}
                disabled={paymentLoading}
                className="flex-1 bg-emerald-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-emerald-700 transition disabled:opacity-50">
                {paymentLoading ? 'Processing...' : 'Record Payment'}
              </button>
              <button 
                onClick={() => setPaymentModal(null)}
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
