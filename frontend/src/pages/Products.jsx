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
  const [products, setProducts] = useState([])
  const [branches, setBranches] = useState([])
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [expanded, setExpanded] = useState(null)

  const [form, setForm] = useState({
    name: '',
    base_price: '',
    branch: '',
    category: '',
    low_stock_threshold: 5,
    variants: [] // dynamic variant list
  })

  // ================= SAFE HELPERS =================
  const safeNumber = (val) => {
    const num = Number(val)
    return isNaN(num) ? 0 : num
  }

  const getTotalStock = (p) => {
    if (!p.variants || p.variants.length === 0) return safeNumber(p.stock_quantity)
    return p.variants.reduce((sum, v) => sum + safeNumber(v.available_quantity), 0)
  }

  const getPrice = (p) => safeNumber(p.base_price)

  // ================= LOAD =================
  useEffect(() => {
    const load = async () => {
      try {
        const [b, c] = await Promise.all([getBranches(), getCategories()])
        setBranches(b.data || [])
        setCategories(c.data || [])
        if (b.data?.length && !selectedBranch) setSelectedBranch(b.data[0])
      } catch {
        toast.error('Failed to load data')
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (!selectedBranch) return
    setLoading(true)
    getProducts({ branch: selectedBranch.id })
      .then(res => setProducts(res.data || []))
      .catch(() => toast.error('Failed to load products'))
      .finally(() => setLoading(false))

    setForm(f => ({ ...f, branch: selectedBranch.id }))
  }, [selectedBranch])

  // ================= FILTER =================
  const filteredProducts = useMemo(() => {
    return products.filter(p =>
      p.name?.toLowerCase().includes(search.toLowerCase())
    )
  }, [products, search])

  // ================= CRUD =================
  const handleSubmit = async (e) => {
    e.preventDefault()
    const payload = {
      ...form,
      base_price: safeNumber(form.base_price),
      variants: form.variants.map(v => ({
        ...v,
        available_quantity: safeNumber(v.available_quantity)
      }))
    }

    try {
      if (editingProduct) {
        const res = await updateProduct(editingProduct.id, payload)
        setProducts(prev => prev.map(p => p.id === res.data.id ? res.data : p))
        toast.success('Product updated')
      } else {
        const res = await createProduct(payload)
        setProducts(prev => [res.data, ...prev])
        toast.success('Product created')
      }
      resetForm()
    } catch {
      toast.error('Error saving product')
    }
  }

  const handleEdit = (p) => {
    setEditingProduct(p)
    setForm({
      ...p,
      base_price: safeNumber(p.base_price),
      variants: p.variants?.length ? p.variants : [],
      branch: selectedBranch.id
    })
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete product?')) return
    try {
      await deleteProduct(id)
      setProducts(prev => prev.filter(p => p.id !== id))
      toast.success('Deleted')
    } catch {
      toast.error('Delete failed')
    }
  }

  const resetForm = () => {
    setShowForm(false)
    setEditingProduct(null)
    setForm({
      name: '',
      base_price: '',
      branch: selectedBranch?.id || '',
      category: '',
      low_stock_threshold: 5,
      variants: []
    })
  }

  // ================= UI =================
  return (
    <div className="p-6 space-y-6">

      {/* HEADER */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Products</h1>
        <button
          onClick={() => setShowForm(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700"
        >
          + Add Product
        </button>
      </div>

      {/* SEARCH */}
      <div className="relative">
        <input
          placeholder="Search products..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full border px-10 py-2 rounded-lg text-sm"
        />
        <span className="absolute left-3 top-2.5 text-gray-400">🔍</span>
      </div>

      {/* TABLE */}
      <div className="bg-white rounded-xl border overflow-hidden">
        {loading ? (
          <div className="p-6 text-center text-gray-400">Loading...</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="p-3 text-left">Product</th>
                <th className="text-left">Price</th>
                <th className="text-left">Stock</th>
                <th className="text-left">Status</th>
                <th className="text-right pr-4">Actions</th>
              </tr>
            </thead>

            <tbody>
              {filteredProducts.map(p => {
                const stock = getTotalStock(p)
                const isLow = stock <= (p.low_stock_threshold || 5)
                const price = getPrice(p)

                return (
                  <>
                    {/* MAIN ROW */}
                    <tr key={p.id} className="border-t hover:bg-gray-50">
                      <td className="p-3 font-medium flex items-center gap-2">
                        {p.variants?.length > 0 && (
                          <button
                            onClick={() => setExpanded(expanded === p.id ? null : p.id)}
                            className="text-xs bg-gray-200 px-2 rounded"
                          >
                            {expanded === p.id ? '-' : '+'}
                          </button>
                        )}
                        {p.name}
                      </td>

                      <td className="font-semibold">${price.toFixed(2)}</td>
                      <td>{stock}</td>

                      <td>
                        <span className={`text-xs px-2 py-1 rounded ${
                          stock === 0
                            ? 'bg-red-100 text-red-600'
                            : isLow
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-green-100 text-green-700'
                        }`}>
                          {stock === 0 ? 'Out of Stock' : isLow ? 'Low Stock' : 'In Stock'}
                        </span>
                      </td>

                      <td className="text-right pr-4 space-x-4">
                        <button onClick={() => handleEdit(p)} className="text-indigo-600 hover:underline">✏️ Edit</button>
                        <button onClick={() => handleDelete(p.id)} className="text-red-500 hover:underline">🗑 Delete</button>
                      </td>
                    </tr>

                    {/* VARIANTS ROW */}
                    {expanded === p.id && p.variants?.length > 0 && (
                      <tr className="bg-gray-50">
                        <td colSpan="5" className="p-3">
                          <div className="grid grid-cols-3 gap-3 text-xs">
                            {p.variants.map((v, i) => (
                              <div key={i} className="border p-2 rounded bg-white">
                                <div className="font-medium">{v.type}</div>
                                <div>Stock: {safeNumber(v.available_quantity)}</div>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* MODAL */}
      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex justify-center items-center">
          <form onSubmit={handleSubmit} className="bg-white p-6 rounded-xl w-[480px] space-y-3">
            <h2 className="font-semibold">{editingProduct ? 'Edit Product' : 'New Product'}</h2>

            <input
              placeholder="Product name"
              value={form.name}
              onChange={e => setForm({...form, name: e.target.value})}
              className="w-full border px-2 py-2 rounded"
              required
            />

            <input
              type="number"
              placeholder="Price"
              value={form.base_price}
              onChange={e => setForm({...form, base_price: e.target.value})}
              className="w-full border px-2 py-2 rounded"
              required
            />

            {/* VARIANTS */}
            <div className="space-y-2">
              <label className="font-medium">Variants</label>
              {form.variants.map((v, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <input
                    placeholder="Variant type (e.g., Red - Large)"
                    value={v.type}
                    onChange={e => {
                      const newVariants = [...form.variants]
                      newVariants[i].type = e.target.value
                      setForm({...form, variants: newVariants})
                    }}
                    className="border px-2 py-1 rounded flex-1"
                    required
                  />
                  <input
                    type="number"
                    placeholder="Stock"
                    value={v.available_quantity}
                    onChange={e => {
                      const newVariants = [...form.variants]
                      newVariants[i].available_quantity = Number(e.target.value)
                      setForm({...form, variants: newVariants})
                    }}
                    className="border px-2 py-1 rounded w-24"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const newVariants = form.variants.filter((_, idx) => idx !== i)
                      setForm({...form, variants: newVariants})
                    }}
                    className="text-red-500 px-2"
                  >
                    🗑
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setForm({...form, variants: [...form.variants, { type: '', available_quantity: 0 }]})}
                className="text-sm text-indigo-600 hover:underline"
              >
                + Add Variant
              </button>
            </div>

            <div className="flex gap-2">
              <button className="flex-1 bg-indigo-600 text-white py-2 rounded">Save</button>
              <button type="button" onClick={resetForm} className="flex-1 border py-2 rounded">Cancel</button>
            </div>
          </form>
        </div>
      )}

    </div>
  )
}