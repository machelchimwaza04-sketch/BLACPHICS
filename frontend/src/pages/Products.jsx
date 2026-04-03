import { useEffect, useState, useMemo } from 'react'
import {
  getProducts,
  getBranches,
  createProduct,
  getCategories,
  deleteProduct,
  updateProduct
} from '../api/api'
import { useBranch } from '../context/BranchContext'
import toast from 'react-hot-toast'

export default function Products() {

  const { selectedBranch, setSelectedBranch } = useBranch()

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const [products, setProducts] = useState([])
  const [branches, setBranches] = useState([])
  const [categories, setCategories] = useState([])

  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)

  const [editingProduct, setEditingProduct] = useState(null)

  const [form, setForm] = useState({
    name: '',
    description: '',
    item_type: 'plain',
    base_price: '',
    customization_price: 0,
    stock_quantity: 0,
    low_stock_threshold: 5,
    branch: '',
    category: '',
  })

  // ✅ Load branches + categories
  useEffect(() => {
    const load = async () => {
      try {
        const [b, c] = await Promise.all([
          getBranches(),
          getCategories()
        ])

        const branchList = Array.isArray(b.data) ? b.data : b.data?.results || []
        const categoryList = Array.isArray(c.data) ? c.data : c.data?.results || []

        setBranches(branchList)
        setCategories(categoryList)

        if (branchList.length && !selectedBranch) {
          setSelectedBranch(branchList[0])
        }

      } catch (err) {
        console.error(err)
        toast.error('Failed to load initial data')
      }
    }

    load()
  }, [])

  // ✅ Load products when branch changes
  useEffect(() => {
    if (!selectedBranch) return

    setLoading(true)

    getProducts({ branch: selectedBranch.id })
      .then(res => {
        const data = Array.isArray(res.data) ? res.data : res.data?.results || []
        setProducts(data)
      })
      .catch(err => {
        console.error(err)
        toast.error('Failed to load products')
      })
      .finally(() => setLoading(false))

    // sync form branch
    setForm(f => ({ ...f, branch: selectedBranch.id }))

  }, [selectedBranch])

  // ✅ Submit
  const handleSubmit = async (e) => {
    e.preventDefault()

    try {
      if (editingProduct) {
        const res = await updateProduct(editingProduct.id, form)

        setProducts(prev =>
          prev.map(p => (p.id === res.data.id ? res.data : p))
        )

        toast.success('Product updated')
      } else {
        const res = await createProduct(form)
        setProducts(prev => [res.data, ...prev])
        toast.success('Product created')
      }

      resetForm()

    } catch (err) {
      console.error(err)
      toast.error('Something went wrong')
    }
  }

  const resetForm = () => {
    setShowForm(false)
    setEditingProduct(null)

    setForm({
      name: '',
      description: '',
      item_type: 'plain',
      base_price: '',
      customization_price: 0,
      stock_quantity: 0,
      low_stock_threshold: 5,
      branch: selectedBranch?.id || '',
      category: '',
    })
  }

  // ✅ Filters (optimized)
  const filteredProducts = useMemo(() => {
    return products.filter(p => {
      const matchesSearch =
        p.name?.toLowerCase().includes(search.toLowerCase()) ||
        p.item_type?.toLowerCase().includes(search.toLowerCase())

      const matchesType =
        typeFilter ? p.item_type === typeFilter : true

      const matchesStatus =
        statusFilter
          ? (statusFilter === 'active' ? p.is_active : !p.is_active)
          : true

      return matchesSearch && matchesType && matchesStatus
    })
  }, [products, search, typeFilter, statusFilter])

  // ✅ Edit
  const handleEdit = (product) => {
    setEditingProduct(product)
    setForm({
      ...product,
      branch: selectedBranch?.id
    })
    setShowForm(true)
  }

  // ✅ Delete
  const handleDelete = async (id) => {
    if (!confirm('Delete this product?')) return

    try {
      await deleteProduct(id)
      setProducts(prev => prev.filter(p => p.id !== id))
      toast.success('Product deleted')
    } catch {
      toast.error('Delete failed')
    }
  }

  return (
    <div className="p-6 space-y-6">

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Products</h1>
          <p className="text-gray-500 text-sm">
            Manage inventory per branch
          </p>
        </div>

        <button
          onClick={() => setShowForm(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700"
        >
          + Add product
        </button>
      </div>

      {/* Branch selector */}
      <div className="flex gap-2 flex-wrap">
        {branches.map(b => (
          <button
            key={b.id}
            onClick={() => setSelectedBranch(b)}
            className={`px-3 py-1 rounded-full text-sm ${
              selectedBranch?.id === b.id
                ? 'bg-indigo-100 text-indigo-700'
                : 'bg-gray-100 text-gray-600'
            }`}
          >
            {b.name}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 bg-white p-4 rounded-xl border">
        <input
          placeholder="Search..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="border px-3 py-2 rounded-lg text-sm"
        />

        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          className="border px-3 py-2 rounded-lg text-sm"
        >
          <option value="">All Types</option>
          <option value="plain">Plain</option>
          <option value="customizable">Customizable</option>
        </select>

        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="border px-3 py-2 rounded-lg text-sm"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border">
        {loading ? (
          <div className="p-6 text-center text-gray-400">
            Loading...
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="p-6 text-center text-gray-400">
            No products found
          </div>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {filteredProducts.map(p => (
                <tr key={p.id} className="border-t">
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2">{p.item_type}</td>
                  <td className="px-4 py-2">${p.base_price}</td>
                  <td className="px-4 py-2">{p.stock_quantity}</td>
                  <td className="px-4 py-2">
                    {p.is_active ? 'Active' : 'Inactive'}
                  </td>
                  <td className="px-4 py-2 flex gap-2">
                    <button onClick={() => handleEdit(p)}>Edit</button>
                    <button onClick={() => handleDelete(p.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}