import { useEffect, useMemo, useState } from 'react'
import { getCustomers, createCustomer, getBranches } from '../api/api'

const paymentStyle = {
  unpaid:  'bg-rose-50 text-rose-700',
  partial: 'bg-yellow-50 text-yellow-700',
  deposit: 'bg-amber-50 text-amber-700',
  paid:    'bg-emerald-50 text-emerald-700',
}
const statusStyle = {
  pending:     'bg-yellow-50 text-yellow-700',
  confirmed:   'bg-blue-50 text-blue-700',
  in_progress: 'bg-indigo-50 text-indigo-700',
  ready:       'bg-purple-50 text-purple-700',
  completed:   'bg-emerald-50 text-emerald-700',
  cancelled:   'bg-rose-50 text-rose-700',
}

const emptyForm = () => ({
  first_name: '', last_name: '', email: '',
  phone: '', gender: '', address: '',
})

export default function Customers() {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [customers, setCustomers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCustomer, setSelectedCustomer] = useState(null)
  const [form, setForm] = useState(emptyForm())

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
    getCustomers(selectedBranch.id)
      .then(r => setCustomers(Array.isArray(r.data) ? r.data : r.data?.results || []))
      .catch(() => setCustomers([]))
      .finally(() => setLoading(false))
  }, [selectedBranch])

  const filtered = useMemo(() =>
    customers.filter(c =>
      `${c.first_name} ${c.last_name}`.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.phone?.includes(searchTerm)
    )
  , [customers, searchTerm])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.gender) return alert('Please select a gender')
    try {
      const res = await createCustomer({
        ...form,
        email: form.email.trim() || null,
        branch: selectedBranch?.id,
      })
      setCustomers(prev => [res.data, ...prev])
      setShowForm(false)
      setForm(emptyForm())
    } catch (err) {
      alert('Failed to create customer: ' + JSON.stringify(err.response?.data))
    }
  }
    return (
    <div className="p-8">

      {/* header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Customers</h1>
          <p className="text-sm text-gray-400 mt-0.5">Customer profiles and order history</p>
        </div>
        <div className="flex gap-3">
          <select value={selectedBranch?.id || ''} onChange={e => setSelectedBranch(branches.find(b => b.id === parseInt(e.target.value)))}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none">
            {branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button onClick={() => setShowForm(true)}
            className="bg-indigo-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-indigo-700 transition">
            + Add customer
          </button>
        </div>
      </div>

      {/* search */}
      <input placeholder="Search by name or phone..." value={searchTerm}
        onChange={e => setSearchTerm(e.target.value)}
        className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm mb-5 focus:outline-none focus:ring-2 focus:ring-indigo-300" />

      <div className="flex gap-6">

        {/* customer list */}
        <div className="flex-1 bg-white rounded-xl border border-gray-100 overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 text-sm">Loading customers...</div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">No customers found.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
                <tr>
                  <th className="px-5 py-3 text-left">Name</th>
                  <th className="px-5 py-3 text-left">Phone</th>
                  <th className="px-5 py-3 text-left">Orders</th>
                  <th className="px-5 py-3 text-left">Total spent</th>
                  <th className="px-5 py-3 text-left">Outstanding</th>
                  <th className="px-5 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map(c => (
                  <tr key={c.id} onClick={() => setSelectedCustomer(c)}
                    className={`hover:bg-indigo-50 cursor-pointer transition ${selectedCustomer?.id === c.id ? 'bg-indigo-50' : ''}`}>
                    <td className="px-5 py-3">
                      <p className="font-medium text-gray-800">{c.first_name} {c.last_name}</p>
                      <p className="text-xs text-gray-400">{c.email || 'No email'}</p>
                    </td>
                    <td className="px-5 py-3 text-gray-600">{c.phone}</td>
                    <td className="px-5 py-3 text-gray-600">{c.total_orders ?? 0}</td>
                    <td className="px-5 py-3 font-medium text-gray-800">${toNum(c.total_spent).toFixed(2)}</td>
                    <td className={`px-5 py-3 font-medium ${toNum(c.outstanding_balance) > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                      ${toNum(c.outstanding_balance).toFixed(2)}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${c.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                        {c.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* customer detail panel */}
        {selectedCustomer && (
          <div className="w-96 bg-white rounded-xl border border-gray-100 flex flex-col">
            <div className="px-5 py-4 border-b border-gray-100">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-semibold text-gray-800">{selectedCustomer.first_name} {selectedCustomer.last_name}</h2>
                  <p className="text-xs text-gray-400 mt-0.5">{selectedCustomer.phone} · {selectedCustomer.email || 'No email'}</p>
                </div>
                <button onClick={() => setSelectedCustomer(null)} className="text-gray-300 hover:text-gray-500 text-lg">×</button>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-3">
                <div className="bg-gray-50 rounded-lg px-3 py-2 text-center">
                  <p className="text-xs text-gray-400">Orders</p>
                  <p className="text-lg font-bold text-gray-700">{selectedCustomer.total_orders ?? 0}</p>
                </div>
                <div className="bg-emerald-50 rounded-lg px-3 py-2 text-center">
                  <p className="text-xs text-emerald-400">Spent</p>
                  <p className="text-lg font-bold text-emerald-700">${toNum(selectedCustomer.total_spent).toFixed(0)}</p>
                </div>
                <div className={`rounded-lg px-3 py-2 text-center ${toNum(selectedCustomer.outstanding_balance) > 0 ? 'bg-rose-50' : 'bg-gray-50'}`}>
                  <p className={`text-xs ${toNum(selectedCustomer.outstanding_balance) > 0 ? 'text-rose-400' : 'text-gray-400'}`}>Owes</p>
                  <p className={`text-lg font-bold ${toNum(selectedCustomer.outstanding_balance) > 0 ? 'text-rose-600' : 'text-gray-400'}`}>
                    ${toNum(selectedCustomer.outstanding_balance).toFixed(0)}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Order history</p>
              {!selectedCustomer.recent_orders?.length ? (
                <p className="text-sm text-gray-400">No orders yet.</p>
              ) : (
                <div className="space-y-2">
                  {selectedCustomer.recent_orders.map(o => (
                    <div key={o.id} className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                      <div className="flex justify-between items-start mb-1.5">
                        <div>
                          <p className="text-sm font-medium text-gray-800 font-mono">{o.order_number}</p>
                          <p className="text-xs text-gray-400">{new Date(o.created_at).toLocaleDateString()}</p>
                        </div>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusStyle[o.status] || 'bg-gray-100 text-gray-500'}`}>
                          {o.status}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className={`px-2 py-0.5 rounded-full font-medium ${paymentStyle[o.payment_status] || 'bg-gray-100 text-gray-500'}`}>
                          {o.payment_status}
                        </span>
                        <div className="text-right">
                          <p className="font-medium text-gray-700">${toNum(o.total_amount).toFixed(2)}</p>
                          {toNum(o.balance_due) > 0 && (
                            <p className="text-rose-500">Owes ${toNum(o.balance_due).toFixed(2)}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* add customer modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">New customer</h2>
            <form onSubmit={handleSubmit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">First name</label>
                  <input required value={form.first_name} onChange={e => setForm({...form, first_name: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Last name</label>
                  <input required value={form.last_name} onChange={e => setForm({...form, last_name: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Phone</label>
                <input required value={form.phone} onChange={e => setForm({...form, phone: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Email (optional)</label>
                <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Gender</label>
                  <select required value={form.gender} onChange={e => setForm({...form, gender: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                    <option value="">— Select —</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Address</label>
                  <input value={form.address} onChange={e => setForm({...form, address: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700">Save</button>
                <button type="button" onClick={() => { setShowForm(false); setForm(emptyForm()) }}
                  className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm hover:bg-gray-50">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}