import { useEffect, useState } from 'react'
import {
  getSupplierSummary, getSupplierPurchases,
  createSupplier, updateSupplier,
  getBranches, createPurchase, updatePurchase, recordPayment
} from '../api/api'

const accountStyle = {
  clear:       'bg-emerald-50 text-emerald-700',
  outstanding: 'bg-yellow-50 text-yellow-700',
  overdue:     'bg-rose-50 text-rose-700',
}
const accountLabel = {
  clear: 'Clear', outstanding: 'Outstanding', overdue: 'Overdue',
}

const paymentStyle = {
  unpaid:  'bg-rose-50 text-rose-700',
  partial: 'bg-yellow-50 text-yellow-700',
  paid:    'bg-emerald-50 text-emerald-700',
}

const statusStyle = {
  ordered:            'bg-blue-50 text-blue-700',
  received:           'bg-emerald-50 text-emerald-700',
  partially_received: 'bg-yellow-50 text-yellow-700',
  cancelled:          'bg-rose-50 text-rose-700',
}

const emptySupplierForm = () => ({
  name: '', contact_person: '', email: '', phone: '', address: '',
})

const emptyPurchaseForm = (branchId = '') => ({
  purchase_number: '', supplier: '', branch: branchId,
  total_amount: '', amount_paid: 0, purchase_date: '',
  expected_delivery: '', notes: '', status: 'ordered', payment_status: 'unpaid',
})

export default function Suppliers() {
  const [suppliers, setSuppliers] = useState([])
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedSupplier, setSelectedSupplier] = useState(null)
  const [supplierPurchases, setSupplierPurchases] = useState([])
  const [loadingPurchases, setLoadingPurchases] = useState(false)
  const [showSupplierForm, setShowSupplierForm] = useState(false)
  const [showPurchaseForm, setShowPurchaseForm] = useState(false)
  const [supplierForm, setSupplierForm] = useState(emptySupplierForm())
  const [purchaseForm, setPurchaseForm] = useState(emptyPurchaseForm())
  const [editingSupplier, setEditingSupplier] = useState(null)
  const [paymentModal, setPaymentModal] = useState(null)
  const [paymentAmount, setPaymentAmount] = useState('')

  const toNum = (v) => Number(v) || 0

  useEffect(() => {
    getBranches().then(r => {
      setBranches(r.data)
      if (r.data.length > 0) {
        setSelectedBranch(r.data[0])
        setPurchaseForm(f => ({ ...f, branch: r.data[0].id }))
      }
    })
  }, [])

  useEffect(() => {
    setLoading(true)
    getSupplierSummary()
      .then(r => setSuppliers(r.data))
      .finally(() => setLoading(false))
  }, [])

  const openSupplier = (supplier) => {
    setSelectedSupplier(supplier)
    setLoadingPurchases(true)
    getSupplierPurchases(supplier.id)
      .then(r => setSupplierPurchases(r.data))
      .finally(() => setLoadingPurchases(false))
  }

  const totalOwed = suppliers.reduce((s, sup) => s + toNum(sup.total_owed), 0)
  const overdueCount = suppliers.filter(s => s.account_status === 'overdue').length

  const handleSupplierSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingSupplier) {
        const res = await updateSupplier(editingSupplier.id, supplierForm)
        setSuppliers(prev => prev.map(s => s.id === res.data.id ? { ...s, ...res.data } : s))
      } else {
        await createSupplier(supplierForm)
        const r = await getSupplierSummary()
        setSuppliers(r.data)
      }
      setShowSupplierForm(false)
      setEditingSupplier(null)
      setSupplierForm(emptySupplierForm())
    } catch (err) {
      alert('Error: ' + JSON.stringify(err.response?.data))
    }
  }

  const handlePurchaseSubmit = async (e) => {
    e.preventDefault()
    try {
      await createPurchase({ ...purchaseForm, branch: selectedBranch?.id })
      if (selectedSupplier) {
        const r = await getSupplierPurchases(selectedSupplier.id)
        setSupplierPurchases(r.data)
      }
      const r2 = await getSupplierSummary()
      setSuppliers(r2.data)
      setShowPurchaseForm(false)
      setPurchaseForm(emptyPurchaseForm(selectedBranch?.id))
    } catch (err) {
      alert('Error: ' + JSON.stringify(err.response?.data))
    }
  }

  const handleMarkReceived = async (purchase) => {
    try {
      await updatePurchase(purchase.id, { ...purchase, status: 'received' })
      if (selectedSupplier) {
        const r = await getSupplierPurchases(selectedSupplier.id)
        setSupplierPurchases(r.data)
        const r2 = await getSupplierSummary()
        setSuppliers(r2.data)
      }
    } catch {
      alert('Could not update status')
    }
  }

  const handleRecordPayment = async () => {
    const amount = toNum(paymentAmount)
    if (!amount || amount <= 0) return alert('Enter a valid amount')
    try {
      await recordPayment(paymentModal.id, amount)
      if (selectedSupplier) {
        const r = await getSupplierPurchases(selectedSupplier.id)
        setSupplierPurchases(r.data)
        const r2 = await getSupplierSummary()
        setSuppliers(r2.data)
        setSelectedSupplier(prev => ({
          ...prev,
          total_owed: r2.data.find(s => s.id === prev.id)?.total_owed ?? prev.total_owed
        }))
      }
      setPaymentModal(null)
      setPaymentAmount('')
    } catch (err) {
      alert('Payment failed: ' + JSON.stringify(err.response?.data))
    }
  }
    return (
    <div className="p-8">

      {/* header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Suppliers</h1>
          <p className="text-sm text-gray-400 mt-0.5">Accounts payable and purchase history</p>
        </div>
        <div className="flex gap-3">
          <select value={selectedBranch?.id || ''}
            onChange={e => setSelectedBranch(branches.find(b => b.id === parseInt(e.target.value)))}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none">
            {branches.map(b => <option key={b.id} value={b.id}>{b.name} — {b.city}</option>)}
          </select>
          <button onClick={() => setShowPurchaseForm(true)}
            className="text-sm border border-indigo-200 text-indigo-600 px-4 py-2 rounded-lg hover:bg-indigo-50 transition">
            + New purchase
          </button>
          <button onClick={() => setShowSupplierForm(true)}
            className="text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition">
            + Add supplier
          </button>
        </div>
      </div>

      {/* AP summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-4">
          <p className="text-xs text-gray-400 mb-1">Total accounts payable</p>
          <p className="text-2xl font-bold text-rose-600">${totalOwed.toFixed(2)}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-4">
          <p className="text-xs text-gray-400 mb-1">Total suppliers</p>
          <p className="text-2xl font-bold text-gray-800">{suppliers.length}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-4">
          <p className="text-xs text-gray-400 mb-1">Overdue accounts</p>
          <p className={`text-2xl font-bold ${overdueCount > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>{overdueCount}</p>
        </div>
      </div>

      <div className="flex gap-6">

        {/* supplier list */}
        <div className="flex-1 bg-white rounded-xl border border-gray-100 overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 text-sm">Loading suppliers...</div>
          ) : suppliers.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">No suppliers yet.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
                <tr>
                  <th className="px-5 py-3 text-left">Supplier</th>
                  <th className="px-5 py-3 text-left">Purchases</th>
                  <th className="px-5 py-3 text-left">Balance owed</th>
                  <th className="px-5 py-3 text-left">Account</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {suppliers.map(s => (
                  <tr key={s.id}
                    onClick={() => openSupplier(s)}
                    className={`hover:bg-indigo-50 cursor-pointer transition ${selectedSupplier?.id === s.id ? 'bg-indigo-50' : ''}`}>
                    <td className="px-5 py-3">
                      <p className="font-medium text-gray-800">{s.name}</p>
                      <p className="text-xs text-gray-400">{s.contact_person || s.phone}</p>
                    </td>
                    <td className="px-5 py-3 text-gray-600">{s.total_purchases}</td>
                    <td className={`px-5 py-3 font-semibold ${toNum(s.total_owed) > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                      ${toNum(s.total_owed).toFixed(2)}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${accountStyle[s.account_status]}`}>
                        {accountLabel[s.account_status]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* supplier detail panel */}
        {selectedSupplier && (
          <div className="w-96 bg-white rounded-xl border border-gray-100 flex flex-col">
            <div className="px-5 py-4 border-b border-gray-100">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-semibold text-gray-800">{selectedSupplier.name}</h2>
                  <p className="text-xs text-gray-400 mt-0.5">{selectedSupplier.phone} · {selectedSupplier.email || 'No email'}</p>
                </div>
                <button onClick={() => setSelectedSupplier(null)} className="text-gray-300 hover:text-gray-500 text-lg">×</button>
              </div>
              <div className="mt-3 flex gap-3">
                <div className="flex-1 bg-rose-50 rounded-lg px-3 py-2 text-center">
                  <p className="text-xs text-rose-400">Balance owed</p>
                  <p className="text-lg font-bold text-rose-600">${toNum(selectedSupplier.total_owed).toFixed(2)}</p>
                </div>
                <div className="flex-1 bg-gray-50 rounded-lg px-3 py-2 text-center">
                  <p className="text-xs text-gray-400">Purchases</p>
                  <p className="text-lg font-bold text-gray-700">{selectedSupplier.total_purchases}</p>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Purchase history</p>
              {loadingPurchases ? (
                <p className="text-sm text-gray-400">Loading...</p>
              ) : supplierPurchases.length === 0 ? (
                <p className="text-sm text-gray-400">No purchases yet.</p>
              ) : (
                <div className="space-y-3">
                  {supplierPurchases.map(p => {
                    const bal = toNum(p.total_amount) - toNum(p.amount_paid)
                    return (
                      <div key={p.id} className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <p className="text-sm font-medium text-gray-800">{p.purchase_number}</p>
                            <p className="text-xs text-gray-400">{p.purchase_date}</p>
                          </div>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusStyle[p.status]}`}>
                            {p.status.replace('_', ' ')}
                          </span>
                        </div>
                        <div className="text-xs space-y-1">
                          <div className="flex justify-between text-gray-500"><span>Total</span><span>${toNum(p.total_amount).toFixed(2)}</span></div>
                          <div className="flex justify-between text-gray-500"><span>Paid</span><span>${toNum(p.amount_paid).toFixed(2)}</span></div>
                          <div className={`flex justify-between font-semibold ${bal > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                            <span>Balance</span><span>${bal.toFixed(2)}</span>
                          </div>
                        </div>
                        <div className="flex gap-2 mt-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${paymentStyle[p.payment_status]}`}>
                            {p.payment_status}
                          </span>
                          {bal > 0 && (
                            <button onClick={() => { setPaymentModal(p); setPaymentAmount('') }}
                              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium ml-auto">
                              Record payment
                            </button>
                          )}
                          {p.status === 'ordered' && (
                            <button onClick={() => handleMarkReceived(p)}
                              className="text-xs text-emerald-600 hover:text-emerald-800 font-medium">
                              Mark received
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* add supplier modal */}
      {showSupplierForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">{editingSupplier ? 'Edit supplier' : 'New supplier'}</h2>
            <form onSubmit={handleSupplierSubmit} className="space-y-3">
              {[
                { label: 'Company name', key: 'name', required: true },
                { label: 'Contact person', key: 'contact_person' },
                { label: 'Phone', key: 'phone', required: true },
                { label: 'Email', key: 'email', type: 'email' },
                { label: 'Address', key: 'address' },
              ].map(f => (
                <div key={f.key}>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">{f.label}</label>
                  <input required={f.required} type={f.type || 'text'}
                    value={supplierForm[f.key]} onChange={e => setSupplierForm({...supplierForm, [f.key]: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
              ))}
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700">Save</button>
                <button type="button" onClick={() => { setShowSupplierForm(false); setEditingSupplier(null); setSupplierForm(emptySupplierForm()) }}
                  className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm hover:bg-gray-50">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* new purchase modal */}
      {showPurchaseForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">New purchase order</h2>
            <form onSubmit={handlePurchaseSubmit} className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Purchase number</label>
                <input required value={purchaseForm.purchase_number} onChange={e => setPurchaseForm({...purchaseForm, purchase_number: e.target.value})}
                  placeholder="e.g. PUR-001"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Supplier</label>
                <select required value={purchaseForm.supplier} onChange={e => setPurchaseForm({...purchaseForm, supplier: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                  <option value="">— Select supplier —</option>
                  {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Total amount ($)</label>
                  <input required type="number" value={purchaseForm.total_amount} onChange={e => setPurchaseForm({...purchaseForm, total_amount: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Amount paid ($)</label>
                  <input type="number" value={purchaseForm.amount_paid} onChange={e => setPurchaseForm({...purchaseForm, amount_paid: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Purchase date</label>
                  <input required type="date" value={purchaseForm.purchase_date} onChange={e => setPurchaseForm({...purchaseForm, purchase_date: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Expected delivery</label>
                  <input type="date" value={purchaseForm.expected_delivery} onChange={e => setPurchaseForm({...purchaseForm, expected_delivery: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Notes</label>
                <textarea rows={2} value={purchaseForm.notes} onChange={e => setPurchaseForm({...purchaseForm, notes: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none resize-none" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700">Save purchase</button>
                <button type="button" onClick={() => setShowPurchaseForm(false)}
                  className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm hover:bg-gray-50">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* record payment modal */}
      {paymentModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-1">Record payment</h2>
            <p className="text-sm text-gray-400 mb-4">Purchase {paymentModal.purchase_number} · Balance ${(toNum(paymentModal.total_amount) - toNum(paymentModal.amount_paid)).toFixed(2)}</p>
            <label className="text-xs font-medium text-gray-500 mb-1 block">Amount paid ($)</label>
            <input type="number" value={paymentAmount} onChange={e => setPaymentAmount(e.target.value)}
              placeholder="0.00" autoFocus
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-indigo-300" />
            <div className="flex gap-3">
              <button onClick={handleRecordPayment}
                className="flex-1 bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700">
                Confirm payment
              </button>
              <button onClick={() => setPaymentModal(null)}
                className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm hover:bg-gray-50">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}