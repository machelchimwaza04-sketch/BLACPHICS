import React from 'react';
import { useEffect, useState, useMemo } from 'react'
import { 
  getProducts, 
  getBranches, 
  createProduct, 
  getCategories, 
  deleteProduct, 
  updateProduct,
  createVariant,
  updateVariant,   
  deleteVariant,
  getProductStats,  
} from '../api/api'
import { motion, AnimatePresence } from 'framer-motion'

const statusStyle = {
  in_stock: 'bg-emerald-100 text-emerald-700',
  low_stock: 'bg-amber-100 text-amber-700',
  out_of_stock: 'bg-rose-100 text-rose-700',
}
const statusLabel = {
  in_stock: 'In stock',
  low_stock: 'Low stock',
  out_of_stock: 'Out of stock',
}

const SIZE_OPTIONS = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL']

const emptyVariant = () => ({
  size: 'M', color: '', stock_quantity: 0,
  cost_price: '', extra_price: 0, is_available: true,
})

const emptyForm = (branchId = '') => ({
  name: '', description: '', item_type: 'plain',
  base_price: '', stock_quantity: 0, low_stock_threshold: 5,
  branch: branchId, category: '', is_active: true,
  variants: [emptyVariant()],
})

export default function Products() {
  const [branches, setBranches] = useState([])
  const [categories, setCategories] = useState([])
  const [products, setProducts] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [form, setForm] = useState(emptyForm())
  const [editingField, setEditingField] = useState(null)
  const [statsData, setStatsData] = useState(null)

  const toNum = (v) => Number(v) || 0

  useEffect(() => {
    Promise.all([getBranches(), getCategories()]).then(([b, c]) => {
      setBranches(b.data)
      setCategories(c.data)
      if (b.data.length > 0) setSelectedBranch(b.data[0])
    })
  }, [])

  useEffect(() => {
    if (!selectedBranch) return
    setLoading(true)

    Promise.all([
      getProducts(selectedBranch.id),
      getProductStats(selectedBranch.id)
    ])
      .then(([productsRes, statsRes]) => {
        setProducts(productsRes.data)
        setStatsData(statsRes.data)
      })
      .finally(() => setLoading(false))

  }, [selectedBranch])

  const filtered = useMemo(() =>
    products.filter(p => p.name?.toLowerCase().includes(search.toLowerCase()))
  , [products, search])

  const stats = useMemo(() => {
    if (!statsData) return {
      totalProducts: 0,
      totalStock: 0,
      lowStock: 0,
      changes: { products: 0, stock: 0, lowStock: 0 }
    }

    const calcChange = (current, prev) => {
      if (!prev || prev === 0) return 0
      return (((current - prev) / prev) * 100).toFixed(1)
    }

    return {
      totalProducts: statsData.current.total_products,
      totalStock: statsData.current.total_stock,
      lowStock: statsData.current.low_stock,

      changes: {
        products: calcChange(
          statsData.current.total_products,
          statsData.previous.total_products
        ),
        stock: 0,       // no history yet
        lowStock: 0
      }
    }
  }, [statsData])

  const overallStatus = (product) => {
    if (!product.variants?.length) return 'out_of_stock'
    const avail = product.variants.map(v => v.available_quantity ?? 0)
    const threshold = product.low_stock_threshold || 5
    if (avail.some(q => q > threshold)) return 'in_stock'
    if (avail.some(q => q > 0)) return 'low_stock'
    return 'out_of_stock'
  }

    const totalAvailable = (product) =>
      product.variants?.reduce((s, v) => s + Math.max(0, toNum(v.available_quantity)), 0)
      ?? Math.max(0, toNum(product.stock_quantity))

  const updateVariantField = (idx, field, val) => {
    const next = [...form.variants]
    next[idx] = { ...next[idx], [field]: val }
    setForm(f => ({ ...f, variants: next }))
  }

  const addVariant = () => setForm(f => ({ ...f, variants: [...f.variants, emptyVariant()] }))

  const removeVariant = (idx) => setForm(f => ({
    ...f, variants: f.variants.filter((_, i) => i !== idx)
  }))

    const handleSubmit = async (e) => {
  e.preventDefault()

  const { variants, ...productData } = form

    const payload = {
    name: form.name,
    description: form.description || '',
    item_type: form.item_type,
    base_price: toNum(form.base_price),
    stock_quantity: toNum(form.stock_quantity),
    low_stock_threshold: toNum(form.low_stock_threshold),
    branch: selectedBranch.id,
    category: form.category || null,
    is_active: form.is_active ?? true,
  }

  // 🚫 prevent duplicates
  const hasDuplicates = variants.some(
    (v, i, arr) =>
      v.color &&
      v.size &&
      arr.findIndex(x => x.size === v.size && x.color === v.color) !== i
  )

  if (hasDuplicates) {
    alert("Duplicate variant (same size + color) not allowed")
    return
  }

  try {
    let productId

    if (editingProduct) {
      const res = await updateProduct(editingProduct.id, payload)
      productId = res.data.id
    } else {
      const res = await createProduct(payload)
      productId = res.data.id
    }

    // 🧹 DELETE removed variants
    if (editingProduct) {
      const existingIds = editingProduct.variants?.map(v => v.id) || []
      const currentIds = variants.filter(v => v.id).map(v => v.id)

      const toDelete = existingIds.filter(id => !currentIds.includes(id))

      await Promise.all(toDelete.map(id => deleteVariant(id)))
    }

        // 🔁 UPDATE existing + ➕ CREATE new variants
    await Promise.all(
      variants
        .filter(v => v.color?.trim() && v.size)
        .map(v => {
          if (v.id) {
            // UPDATE — must include product field
            return updateVariant(v.id, {
              product: productId,
              size: v.size,
              color: v.color,
              stock_quantity: toNum(v.stock_quantity),
              committed_quantity: toNum(v.committed_quantity) || 0,
              cost_price: toNum(v.cost_price),
              extra_price: toNum(v.extra_price),
              is_available: true,
            })
          } else {
            // CREATE new variant
            return createVariant({
              product: productId,
              size: v.size,
              color: v.color,
              stock_quantity: toNum(v.stock_quantity),
              committed_quantity: 0,
              cost_price: toNum(v.cost_price),
              extra_price: toNum(v.extra_price),
              is_available: true,
            })
          }
        })
    )

    // 🔄 refresh
    const refreshed = await getProducts(selectedBranch.id)
    setProducts(refreshed.data)

    resetForm()

  } catch (err) {
    alert('Error saving product: ' + JSON.stringify(err.response?.data || err.message))
  }
}

  const handleEdit = (p) => {
    setEditingProduct(p)
    setForm({
      ...p,
      base_price: toNum(p.base_price),
      branch: selectedBranch.id,
      variants: p.variants?.length ? p.variants.map(v => ({
        ...v,
        cost_price: toNum(v.cost_price),
        extra_price: toNum(v.extra_price),
      })) : [emptyVariant()],
    })
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this product?')) return
    try {
      await deleteProduct(id)
      setProducts(prev => prev.filter(p => p.id !== id))
    } catch {
      alert('Delete failed')
    }
  }

  const resetForm = () => {
    setShowForm(false)
    setEditingProduct(null)
    setForm(emptyForm(selectedBranch?.id))
  }
    return (
    <div className="p-8 bg-slate-50 min-h-screen font-sans">

      {/* header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Products</h1>
          <p className="text-sm text-gray-400 mt-0.5">Manage inventory, variants and cost prices</p>
        </div>
        <div className="flex gap-3">
          <select value={selectedBranch?.id || ''} onChange={e => setSelectedBranch(branches.find(b => b.id === parseInt(e.target.value)))}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300">
            {branches.map(b => <option key={b.id} value={b.id}>{b.name} — {b.city}</option>)}
          </select>
          <button onClick={() => {
            resetForm()
            setShowForm(true)
          }}
            className="bg-blue-500 text-white text-sm px-4 py-2 rounded-xl hover:bg-blue-600 transition shadow-sm">
            + Add product
          </button>
        </div>
      </div>

      {/* search */}
      <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search products..."
        className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm mb-5 focus:outline-none focus:ring-2 focus:ring-indigo-300" />

               <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          {
            title: 'TOTAL PRODUCTS',
            value: stats.totalProducts,
            sub: stats.changes.products !== 0 ? `↗ ${Math.abs(stats.changes.products)}% from last month` : 'No change',
            subColor: stats.changes.products >= 0 ? 'text-emerald-600' : 'text-rose-500',
            icon: '📦', iconBg: 'bg-blue-100',
          },
          {
            title: 'TOTAL STOCK',
            value: stats.totalStock,
            sub: 'Units available across variants',
            subColor: 'text-gray-400',
            icon: '🗂️', iconBg: 'bg-emerald-100',
          },
          {
            title: 'LOW STOCK',
            value: stats.lowStock,
            sub: stats.lowStock > 0 ? `${stats.lowStock} items need restocking` : '✓ All stocked up',
            subColor: stats.lowStock > 0 ? 'text-amber-600' : 'text-emerald-600',
            icon: '⚠️', iconBg: 'bg-amber-100',
          },
          {
            title: 'OUT OF STOCK',
            value: statsData?.current?.out_of_stock ?? 0,
            sub: (statsData?.current?.out_of_stock ?? 0) > 0 ? 'Needs immediate restocking' : '✓ All variants stocked',
            subColor: (statsData?.current?.out_of_stock ?? 0) > 0 ? 'text-rose-600' : 'text-emerald-600',
            icon: '🚫', iconBg: 'bg-rose-100',
          },
        ].map((card, i) => (
          <div key={i} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-400 tracking-widest mb-2">{card.title}</p>
              <p className="text-3xl font-bold text-slate-900 mb-1">{card.value}</p>
              <p className={`text-xs font-medium ${card.subColor}`}>{card.sub}</p>
            </div>
            <div className={`w-11 h-11 flex items-center justify-center rounded-xl ${card.iconBg} shrink-0 ml-3`}>
              <span className="text-xl">{card.icon}</span>
            </div>
          </div>
        ))}
      </div>
   
      {/* product table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {loading ? (
      <div className="p-6 space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-10 bg-slate-100 animate-pulse rounded-lg" />
        ))}
      </div>
    ) : filtered.length === 0 ? (
      <div className="p-12 text-center">
        <div className="text-slate-300 text-4xl mb-3">📦</div>
        <p className="text-slate-500 text-sm">No products found</p>
      </div>
    ) : (
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-400 text-[11px] uppercase tracking-wider sticky top-0 z-10">
            <tr>
              <th className="px-5 py-3 text-left">Product</th>
              <th className="px-5 py-3 text-left">Type</th>
              <th className="px-5 py-3 text-left">Sell price</th>
              <th className="px-5 py-3 text-left">Stock</th>
              <th className="px-5 py-3 text-left">Status</th>
              <th className="px-5 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map(p => {
              const st = overallStatus(p)
              const stock = totalAvailable(p)
              const isExpanded = expanded === p.id
              return (
                <React.Fragment key={p.id}>
                  <tr className="group hover:bg-slate-50/60 transition-colors duration-150 cursor-pointer">
                    {/* Product main row */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        {p.variants?.length > 0 && (
                          <button
                            onClick={() => setExpanded(isExpanded ? null : p.id)}
                            className="w-5 h-5 rounded bg-gray-200 text-gray-600 text-xs flex items-center justify-center hover:bg-gray-300 transition"
                          >
                            {isExpanded ? '−' : '+'}
                          </button>
                        )}
                        <div>
                          {editingField === `name-${p.id}` ? (
                            <input
                              autoFocus
                              defaultValue={p.name}
                              onBlur={async (e) => {
                                await updateProduct(p.id, { name: e.target.value })
                                setEditingField(null)
                                const refreshed = await getProducts(selectedBranch.id)
                                setProducts(refreshed.data)
                              }}
                              className="border px-2 py-1 rounded text-sm"
                            />
                          ) : (
                            <p
                              onDoubleClick={() => setEditingField(`name-${p.id}`)}
                              className="font-medium text-slate-900 cursor-pointer hover:text-indigo-600"
                            >
                              {p.name}
                            </p>
                          )}
                          {p.category_name && (
                            <p className="text-xs text-slate-400">{p.category_name}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          p.item_type === 'customizable'
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {p.item_type}
                      </span>
                    </td>
                    <td className="px-5 py-3 font-medium text-gray-800">
                      ${toNum(p.base_price).toFixed(2)}
                    </td>
                    <td className="px-5 py-3 text-gray-600">{stock} units</td>
                    <td className="px-5 py-3">
                      <span
                        className={`text-xs px-3 py-1 rounded-full font-medium ${statusStyle[st]}`}
                      >
                        {statusLabel[st]}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right">
                    <div className="opacity-0 group-hover:opacity-100 transition flex justify-end gap-3">
                      <button
                        onClick={() => handleEdit(p)}
                        className="text-slate-400 hover:text-slate-700 text-xs"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(p.id)}
                        className="text-slate-400 hover:text-rose-600 text-xs"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                  </tr>

                  {/* Expanded variants row */}
                  <AnimatePresence>
                    {isExpanded && p.variants?.length > 0 && (
                      <tr key={p.id + '-variants'}>
                        <td colSpan="6" className="p-0 border-none">
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.3 }}
                            className="overflow-hidden"
                          >
                            <div className="px-5 py-3 bg-gray-50">
                              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                                Variants & COGS
                              </p>
                              <div className="overflow-x-auto">
                                <table className="w-full text-xs">
                                  <thead>
                                    <tr className="text-gray-400 border-b border-gray-200">
                                      <th className="pb-1 text-left">Size</th>
                                      <th className="pb-1 text-left">Color</th>
                                      <th className="pb-1 text-left">Stock</th>
                                      <th className="pb-1 text-left">Committed</th>
                                      <th className="pb-1 text-left">Available</th>
                                      <th className="pb-1 text-left">Cost price</th>
                                      <th className="pb-1 text-left">Sell price</th>
                                      <th className="pb-1 text-left">Margin</th>
                                      <th className="pb-1 text-left">Status</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-100">
                                    {p.variants.map(v => {
                                      const margin = v.gross_margin
                                      const sellP = toNum(v.selling_price)
                                      return (
                                        <tr key={v.id} className="text-gray-600">
                                          <td className="py-1.5 font-medium">{v.size}</td>
                                          <td className="py-1.5">{v.color}</td>
                                          <td className="py-1.5">{v.stock_quantity}</td>
                                          <td className="py-1.5 text-amber-600">{v.committed_quantity}</td>
                                          <td className="py-1.5 font-medium">{v.available_quantity}</td>
                                          <td className="py-1.5 text-rose-600">
                                            ${toNum(v.cost_price).toFixed(2)}
                                          </td>
                                          <td className="py-1.5 text-emerald-600">${sellP.toFixed(2)}</td>
                                          <td className="py-1.5">
                                            {margin !== null && margin !== undefined ? (
                                              <span
                                                className={`font-medium ${
                                                  toNum(margin) >= 30
                                                    ? 'text-emerald-600'
                                                    : toNum(margin) >= 10
                                                    ? 'text-yellow-600'
                                                    : 'text-rose-600'
                                                }`}
                                              >
                                                {toNum(margin).toFixed(1)}%
                                              </span>
                                            ) : (
                                              <span className="text-gray-300">—</span>
                                            )}
                                          </td>
                                          <td className="py-1.5">
                                            <span
                                              className={`px-2 py-0.5 rounded-full font-medium ${
                                                statusStyle[v.stock_status || 'out_of_stock']
                                              }`}
                                            >
                                              {statusLabel[v.stock_status || 'out_of_stock']}
                                            </span>
                                          </td>
                                        </tr>
                                      )
                                    })}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </motion.div>
                        </td>
                      </tr>
                    )}
                  </AnimatePresence>
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      )}
    </div>

      {/* modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-screen overflow-y-auto">
            <div className="p-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-5">
                {editingProduct ? 'Edit product' : 'New product'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Product name</label>
                    <input required value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Category</label>
                    <select value={form.category} onChange={e => setForm({...form, category: e.target.value})}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                      <option value="">— Select category —</option>
                      {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Item type</label>
                    <select value={form.item_type} onChange={e => setForm({...form, item_type: e.target.value})}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                      <option value="plain">Plain</option>
                      <option value="customizable">Customizable</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Base selling price ($)</label>
                    <input required type="number" step="0.01" value={form.base_price} onChange={e => setForm({...form, base_price: e.target.value})}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Low stock threshold</label>
                    <input type="number" value={form.low_stock_threshold} onChange={e => setForm({...form, low_stock_threshold: e.target.value})}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Description</label>
                    <input value={form.description || ''} onChange={e => setForm({...form, description: e.target.value})}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                  </div>
                </div>

                {/* variants */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Variants (size / color / cost)</label>
                    <button type="button" onClick={addVariant}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-medium">+ Add variant</button>
                  </div>
                  <div className="space-y-2">
                    {form.variants.map((v, i) => (
                      <div key={i} className="grid grid-cols-6 gap-2 items-center bg-gray-50 rounded-lg p-2">
                        <select value={v.size} onChange={e => updateVariantField(i, 'size', e.target.value)}
                          className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none">
                          {SIZE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                        <input placeholder="Color" value={v.color} onChange={e => updateVariantField(i, 'color', e.target.value)}
                          className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none" />
                        <div>
                          <input type="number" placeholder="Stock" value={v.stock_quantity} onChange={e => updateVariantField(i, 'stock_quantity', parseInt(e.target.value) || 0)}
                            className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none" />
                        </div>
                        <div>
                          <input type="number" step="0.01" placeholder="Cost $" value={v.cost_price} onChange={e => updateVariantField(i, 'cost_price', e.target.value)}
                            className="w-full border border-rose-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-rose-300 bg-rose-50" />
                        </div>
                        <div>
                          <input type="number" step="0.01" placeholder="Extra $" value={v.extra_price} onChange={e => updateVariantField(i, 'extra_price', e.target.value)}
                            className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none" />
                        </div>
                        <button type="button" onClick={() => removeVariant(i)}
                          className="text-rose-400 hover:text-rose-600 text-sm font-medium text-center">✕</button>
                      </div>
                    ))}
                    <div className="grid grid-cols-6 gap-2 text-xs text-gray-400 px-2">
                      <span>Size</span><span>Color</span><span>Stock</span>
                      <span className="text-rose-400">Cost price</span><span>Extra price</span><span></span>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button type="submit"
                    className="flex-1 bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700 transition">
                    {editingProduct ? 'Save changes' : 'Create product'}
                  </button>
                  <button type="button" onClick={resetForm}
                    className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm hover:bg-gray-50 transition">
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}