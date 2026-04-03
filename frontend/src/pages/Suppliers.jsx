import { useEffect, useMemo, useState } from 'react'
import {
  getSuppliers,
  createSupplier,
  getPurchases,
  createPurchase
} from '../api/api'
import toast from 'react-hot-toast'
import { useBranch } from '../context/BranchContext'

const statusColors = {
  ordered: 'bg-yellow-50 text-yellow-700',
  received: 'bg-emerald-50 text-emerald-700',
  partially_received: 'bg-blue-50 text-blue-700',
  cancelled: 'bg-rose-50 text-rose-700',
}

const paymentColors = {
  unpaid: 'bg-rose-50 text-rose-700',
  partial: 'bg-yellow-50 text-yellow-700',
  paid: 'bg-emerald-50 text-emerald-700',
}

export default function Suppliers() {
  const { selectedBranch } = useBranch()

  const [suppliers, setSuppliers] = useState([])
  const [purchases, setPurchases] = useState([])

  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('suppliers')
  const [search, setSearch] = useState('')

  const [showSupplierForm, setShowSupplierForm] = useState(false)
  const [showPurchaseForm, setShowPurchaseForm] = useState(false)

  const [supplierForm, setSupplierForm] = useState({
    name: '',
    contact_person: '',
    email: '',
    phone: '',
    address: '',
  })

  const [purchaseForm, setPurchaseForm] = useState({
    purchase_number: '',
    supplier: '',
    total_amount: '',
    amount_paid: 0,
    purchase_date: '',
    expected_delivery: '',
    notes: '',
  })

  // ✅ LOAD SUPPLIERS ONLY (no branches here anymore)
  useEffect(() => {
    getSuppliers()
      .then(res => {
        const data = Array.isArray(res.data)
          ? res.data
          : res.data?.results || []
        setSuppliers(data)
      })
      .catch(() => toast.error('Failed to load suppliers'))
      .finally(() => setLoading(false))
  }, [])

  // ✅ LOAD PURCHASES BASED ON GLOBAL BRANCH
  useEffect(() => {
    if (!selectedBranch) return

    getPurchases(selectedBranch.id)
      .then(res => {
        const data = Array.isArray(res.data)
          ? res.data
          : res.data?.results || []
        setPurchases(data)
      })
      .catch(() => toast.error('Failed to load purchases'))
  }, [selectedBranch])

  // 🔍 FILTERS
  const filteredSuppliers = useMemo(() => {
    return suppliers.filter(s =>
      s.name?.toLowerCase().includes(search.toLowerCase()) ||
      s.phone?.includes(search)
    )
  }, [suppliers, search])

  const filteredPurchases = useMemo(() => {
    return purchases.filter(p =>
      p.purchase_number?.toLowerCase().includes(search.toLowerCase())
    )
  }, [purchases, search])

  // ➕ CREATE SUPPLIER
  const handleSupplierSubmit = async (e) => {
    e.preventDefault()

    try {
      const res = await createSupplier(supplierForm)
      setSuppliers(prev => [res.data, ...prev])

      toast.success('Supplier created')
      setShowSupplierForm(false)

      setSupplierForm({
        name: '',
        contact_person: '',
        email: '',
        phone: '',
        address: '',
      })
    } catch {
      toast.error('Failed to create supplier')
    }
  }

  // ➕ CREATE PURCHASE
  const handlePurchaseSubmit = async (e) => {
    e.preventDefault()

    try {
      const payload = {
        ...purchaseForm,
        branch: selectedBranch?.id,
      }

      const res = await createPurchase(payload)
      setPurchases(prev => [res.data, ...prev])

      toast.success('Purchase created')
      setShowPurchaseForm(false)

      setPurchaseForm({
        purchase_number: '',
        supplier: '',
        total_amount: '',
        amount_paid: 0,
        purchase_date: '',
        expected_delivery: '',
        notes: '',
      })
    } catch {
      toast.error('Failed to create purchase')
    }
  }

  return (
    <div className="p-6 space-y-6">

      {/* HEADER */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold">Suppliers</h1>
          <p className="text-gray-500 text-sm">
            Branch: {selectedBranch?.name || 'Select branch'}
          </p>
        </div>

        <button
          onClick={() =>
            activeTab === 'suppliers'
              ? setShowSupplierForm(true)
              : setShowPurchaseForm(true)
          }
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700"
        >
          {activeTab === 'suppliers' ? '+ Supplier' : '+ Purchase'}
        </button>
      </div>

      {/* SEARCH */}
      <input
        placeholder="Search..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="w-full md:w-1/3 border px-3 py-2 rounded-lg text-sm"
      />

      {/* TABS */}
      <div className="flex gap-2 bg-gray-100 p-1 rounded-lg w-fit">
        {['suppliers', 'purchases'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-1.5 rounded-md text-sm capitalize ${
              activeTab === tab
                ? 'bg-white shadow text-gray-800'
                : 'text-gray-500'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* SUPPLIERS TABLE */}
      {activeTab === 'suppliers' && (
        <div className="bg-white rounded-xl border">
          {loading ? (
            <div className="p-6 text-center">Loading...</div>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {filteredSuppliers.map(s => (
                  <tr key={s.id} className="border-t">
                    <td className="px-4 py-2">{s.name}</td>
                    <td className="px-4 py-2">{s.phone}</td>
                    <td className="px-4 py-2">{s.email || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* PURCHASES TABLE */}
      {activeTab === 'purchases' && (
        <div className="bg-white rounded-xl border">
          <table className="w-full text-sm">
            <tbody>
              {filteredPurchases.map(p => (
                <tr key={p.id} className="border-t">
                  <td className="px-4 py-2">{p.purchase_number}</td>
                  <td className="px-4 py-2">{p.supplier}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 rounded text-xs ${statusColors[p.status]}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 rounded text-xs ${paymentColors[p.payment_status]}`}>
                      {p.payment_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  )
}