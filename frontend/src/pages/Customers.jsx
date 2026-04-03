import { useEffect, useMemo, useState } from 'react'
import { getCustomers, createCustomer } from '../api/api'
import { useBranch } from '../context/BranchContext'
import toast from 'react-hot-toast'

export default function Customers() {
  const { branches, selectedBranch, setSelectedBranch } = useBranch()

  const [customers, setCustomers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    gender: '',
    address: '',
  })

  // ✅ Load customers when branch changes
  useEffect(() => {
    if (!selectedBranch) return

    setLoading(true)

    getCustomers(selectedBranch.id)
      .then(res => {
        const data = Array.isArray(res.data)
          ? res.data
          : res.data?.results || []
        setCustomers(data)
      })
      .catch(() => {
        toast.error('Failed to load customers')
        setCustomers([])
      })
      .finally(() => setLoading(false))
  }, [selectedBranch])

  // ✅ Search optimization
  const filteredCustomers = useMemo(() => {
    return customers.filter(c =>
      `${c.first_name} ${c.last_name}`.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.phone.includes(searchTerm)
    )
  }, [customers, searchTerm])

  // ✅ Submit
  const handleSubmit = e => {
    e.preventDefault()

    if (!form.gender) {
      toast.error('Please select a gender')
      return
    }

    const payload = {
      ...form,
      email: form.email.trim() || null,
      branch: selectedBranch?.id,
    }

    createCustomer(payload)
      .then(res => {
        setCustomers(prev => [res.data, ...prev])
        toast.success('Customer added successfully')

        setShowForm(false)

        setForm({
          first_name: '',
          last_name: '',
          email: '',
          phone: '',
          gender: '',
          address: '',
        })
      })
      .catch(err => {
        console.error(err.response?.data)
        toast.error('Failed to create customer')
      })
  }

  return (
    <div className="p-6 space-y-6">

      {/* HEADER */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold">Customers</h1>
          <p className="text-gray-500 text-sm">
            Manage customer profiles per branch
          </p>
        </div>

        <button
          onClick={() => setShowForm(true)}
          className="bg-indigo-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-indigo-700"
        >
          + Add customer
        </button>
      </div>

      {/* BRANCH SELECTOR */}
      <div className="flex gap-2 flex-wrap">
        {branches.map(b => (
          <button
            key={b.id}
            onClick={() => setSelectedBranch(b)}
            className={`px-4 py-2 rounded-full text-sm border ${
              selectedBranch?.id === b.id
                ? 'bg-indigo-100 border-indigo-600'
                : 'border-gray-200'
            }`}
          >
            {b.name}
          </button>
        ))}
      </div>

      {/* SEARCH */}
      <input
        placeholder="Search by name or phone..."
        value={searchTerm}
        onChange={e => setSearchTerm(e.target.value)}
        className="w-full md:w-1/3 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300"
      />

      {/* TABLE */}
      <div className="bg-white rounded-lg shadow-sm overflow-x-auto">
        {loading ? (
          <div className="p-6 text-center text-gray-400">
            Loading customers...
          </div>
        ) : filteredCustomers.length === 0 ? (
          <div className="p-6 text-center text-gray-400">
            No customers found
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-4 py-2 text-left">Name</th>
                <th className="px-4 py-2 text-left">Phone</th>
                <th className="px-4 py-2 text-left">Email</th>
                <th className="px-4 py-2 text-left">Gender</th>
                <th className="px-4 py-2 text-left">Status</th>
              </tr>
            </thead>

            <tbody className="divide-y">
              {filteredCustomers.map(c => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2">
                    {c.first_name} {c.last_name}
                  </td>
                  <td className="px-4 py-2">{c.phone}</td>
                  <td className="px-4 py-2">{c.email || '—'}</td>

                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      c.gender === 'male'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-pink-100 text-pink-700'
                    }`}>
                      {c.gender || '—'}
                    </span>
                  </td>

                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      c.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-500'
                    }`}>
                      {c.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* MODAL */}
      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex justify-end z-50">
          <div className="bg-white w-full md:w-1/3 h-full p-6 overflow-auto shadow-xl">
            <h2 className="text-lg font-semibold mb-4">New Customer</h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">

                <input
                  placeholder="First Name"
                  value={form.first_name}
                  onChange={e => setForm({ ...form, first_name: e.target.value })}
                  className="input"
                  required
                />

                <input
                  placeholder="Last Name"
                  value={form.last_name}
                  onChange={e => setForm({ ...form, last_name: e.target.value })}
                  className="input"
                  required
                />

                <input
                  placeholder="Email"
                  type="email"
                  value={form.email}
                  onChange={e => setForm({ ...form, email: e.target.value })}
                  className="input"
                />

                <input
                  placeholder="Phone"
                  value={form.phone}
                  onChange={e => setForm({ ...form, phone: e.target.value })}
                  className="input"
                  required
                />

                <select
                  value={form.gender}
                  onChange={e => setForm({ ...form, gender: e.target.value })}
                  className="input"
                  required
                >
                  <option value="">Select gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>

                <input
                  placeholder="Address"
                  value={form.address}
                  onChange={e => setForm({ ...form, address: e.target.value })}
                  className="input"
                />

              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 border rounded-lg text-sm"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm"
                >
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}