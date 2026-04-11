import { useEffect, useState } from 'react'
import { getBranches, getAlerts } from '../api/api'

const statusStyle = {
  out_of_stock: { pill: 'bg-rose-100 text-rose-700', label: 'Out of stock' },
  low_stock:    { pill: 'bg-amber-100 text-amber-700', label: 'Low stock' },
}

export default function Alerts() {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [emailSent, setEmailSent] = useState(false)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    getBranches().then(r => {
      setBranches(r.data)
      if (r.data.length > 0) setSelectedBranch(r.data[0])
    })
  }, [])

  useEffect(() => {
    if (!selectedBranch) return
    setLoading(true)
    setEmailSent(false)
    getAlerts(selectedBranch.id)
      .then(r => setData(r.data))
      .finally(() => setLoading(false))
  }, [selectedBranch])

  const handleSendEmail = async () => {
    setSending(true)
    await getAlerts(selectedBranch.id, true)
    setSending(false)
    setEmailSent(true)
    setTimeout(() => setEmailSent(false), 4000)
  }

  const alerts = data?.alerts ?? []
  const filtered = filter === 'all' ? alerts : alerts.filter(a => a.status === filter)

  return (
    <div className="p-8">

      {/* header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Stock Alerts</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Monitor low and out-of-stock variants across your inventory
          </p>
        </div>

        <div className="flex gap-3">
          <select
            value={selectedBranch?.id || ''}
            onChange={e =>
              setSelectedBranch(branches.find(b => b.id === parseInt(e.target.value)))
            }
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none"
          >
            {branches.map(b => (
              <option key={b.id} value={b.id}>
                {b.name} — {b.city}
              </option>
            ))}
          </select>

          <button
            onClick={handleSendEmail}
            disabled={sending || !alerts.length}
            className="text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-40 transition"
          >
            {sending ? 'Sending...' : emailSent ? '✓ Email sent!' : '📧 Email manager'}
          </button>
        </div>
      </div>

      {/* summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* total */}
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex justify-between">
          <div>
            <p className="text-xs text-gray-400 mb-1">TOTAL ALERTS</p>
            <p className={`text-3xl font-bold ${(data?.count ?? 0) > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
              {data?.count ?? 0}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              {(data?.count ?? 0) === 0 ? '✓ All variants stocked' : 'Requires attention'}
            </p>
          </div>
          <div className="w-11 h-11 bg-rose-50 rounded-xl flex items-center justify-center">🔔</div>
        </div>

        {/* out of stock */}
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex justify-between">
          <div>
            <p className="text-xs text-gray-400 mb-1">OUT OF STOCK</p>
            <p className={`text-3xl font-bold ${(data?.out_of_stock ?? 0) > 0 ? 'text-rose-600' : 'text-gray-400'}`}>
              {data?.out_of_stock ?? 0}
            </p>
            <p className="text-xs text-gray-400 mt-1">Immediate restock needed</p>
          </div>
          <div className="w-11 h-11 bg-rose-50 rounded-xl flex items-center justify-center">🚫</div>
        </div>

        {/* low stock */}
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex justify-between">
          <div>
            <p className="text-xs text-gray-400 mb-1">LOW STOCK</p>
            <p className={`text-3xl font-bold ${(data?.low_stock ?? 0) > 0 ? 'text-amber-600' : 'text-gray-400'}`}>
              {data?.low_stock ?? 0}
            </p>
            <p className="text-xs text-gray-400 mt-1">Below threshold</p>
          </div>
          <div className="w-11 h-11 bg-amber-50 rounded-xl flex items-center justify-center">⚠️</div>
        </div>
      </div>

      {/* filter buttons */}
      <div className="flex gap-2 mb-4">
        {['all', 'out_of_stock', 'low_stock'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-lg text-sm border ${
              filter === f ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600'
            }`}
          >
            {f.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* alerts list */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {loading ? (
          <div className="p-6 text-sm text-gray-400">Loading alerts...</div>
        ) : !filtered.length ? (
          <div className="p-6 text-sm text-gray-400">No alerts found</div>
        ) : (
          <div className="divide-y">
            {filtered.map(a => {
              const style = statusStyle[a.status] || {}
              return (
                <div key={a.id} className="p-4 flex items-center justify-between">
                  
                  {/* product */}
                  <div>
                    <p className="text-sm font-medium text-gray-800">{a.product_name}</p>
                    <p className="text-xs text-gray-400">{a.variant_name}</p>
                  </div>

                  {/* quantity */}
                  <div className="text-sm text-gray-500">
                    Qty: <span className="font-semibold">{a.quantity}</span>
                  </div>

                  {/* status */}
                  <span className={`text-xs px-3 py-1 rounded-full ${style.pill}`}>
                    {style.label}
                  </span>

                </div>
              )
            })}
          </div>
        )}
      </div>

    </div>
  )
}