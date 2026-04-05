import { useEffect, useState, useMemo } from 'react'
import { getBranches, getProducts, getCustomers, createOrder, createOrderItem, getCustomizationServices } from '../api/api'

const stockStyles = {
  in_stock: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  low_stock: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  out_of_stock: 'bg-rose-100 text-rose-700 border-rose-200',
}
const stockDot = { in_stock: 'bg-emerald-500', low_stock: 'bg-yellow-400', out_of_stock: 'bg-rose-500' }
const stockLabel = { in_stock: 'In stock', low_stock: 'Low stock', out_of_stock: 'Out of stock' }

export default function POS() {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [products, setProducts] = useState([])
  const [customers, setCustomers] = useState([])
  const [services, setServices] = useState([])
  const [search, setSearch] = useState('')
  const [cart, setCart] = useState([])
  const [transactionType, setTransactionType] = useState('quick_sale')
  const [selectedCustomer, setSelectedCustomer] = useState(null)
  const [payment, setPayment] = useState({ method: 'cash', amount_paid: 0 })
  const [discount, setDiscount] = useState({ amount: 0, reason: '' })
  const [notes, setNotes] = useState('')
  const [estimatedCompletion, setEstimatedCompletion] = useState('')
  const [orderNumber, setOrderNumber] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(null)

  const toNum = (v) => Number(v) || 0
  const round2 = (n) => Math.round(n * 100) / 100

  useEffect(() => {
    getBranches().then(r => {
      setBranches(r.data)
      if (r.data.length > 0) setSelectedBranch(r.data[0])
    }).catch(() => alert('Could not load branches'))
  }, [])

  useEffect(() => {
    getCustomizationServices().then(r => setServices(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedBranch) return
    Promise.all([getProducts(selectedBranch.id), getCustomers(selectedBranch.id)])
      .then(([p, c]) => { setProducts(p.data); setCustomers(c.data) })
      .catch(() => alert('Could not load products'))
    setCart([])
    setOrderNumber('ORD-' + Date.now().toString().slice(-6))
  }, [selectedBranch])

  const filtered = useMemo(() =>
    products.filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
  , [products, search])

  const addToCart = (product, variant = null) => {
    if (transactionType === 'quick_sale') {
      const st = variant ? variant.stock_status : 'in_stock'
      if (st === 'out_of_stock') { alert('Out of stock. Switch to Custom Order.'); return }
    }
    const key = variant ? product.id + '-' + variant.id : String(product.id)
    const base = toNum(product.base_price)
    const extra = variant ? toNum(variant.extra_price) : 0
    setCart(prev => {
      const ex = prev.find(i => i.key === key)
      if (ex) return prev.map(i => i.key === key ? { ...i, quantity: i.quantity + 1 } : i)
      return [...prev, {
        key, product, variant,
        quantity: 1,
        unit_price: base + extra,
        override_price: null,
        override_reason: '',
        customization_details: '',
        customization_price: 0,
        selected_services: [],
        stock_status: variant ? (variant.stock_status || 'in_stock') : 'in_stock',
      }]
    })
  }

  const updateItem = (key, field, val) =>
    setCart(prev => prev.map(i => i.key === key ? { ...i, [field]: val } : i))

  const removeItem = (key) => setCart(prev => prev.filter(i => i.key !== key))
  const incQty = (key) => setCart(prev => prev.map(i => i.key === key ? { ...i, quantity: i.quantity + 1 } : i))
  const decQty = (key) => setCart(prev => prev.map(i => i.key === key ? { ...i, quantity: Math.max(1, i.quantity - 1) } : i))

  const toggleService = (key, svc) => {
    setCart(prev => prev.map(item => {
      if (item.key !== key) return item
      const has = item.selected_services.find(s => s.id === svc.id)
      const next = has ? item.selected_services.filter(s => s.id !== svc.id) : [...item.selected_services, svc]
      return { ...item, selected_services: next, customization_price: next.reduce((s, x) => s + toNum(x.price), 0) }
    }))
  }

  const subtotal = cart.reduce((sum, i) => {
    const p = (i.override_price !== null && i.override_price !== '') ? toNum(i.override_price) : toNum(i.unit_price)
    return sum + (p + toNum(i.customization_price)) * i.quantity
  }, 0)
  const discAmt = toNum(discount.amount)
  const paidAmt = toNum(payment.amount_paid)
  const total = subtotal - discAmt
  const balance = total - paidAmt

  const checkout = async () => {
    if (!cart.length) return alert('Cart is empty')
    if (!orderNumber) return alert('Order number required')
    setLoading(true)
    try {
      const oRes = await createOrder({
        branch: selectedBranch.id,
        customer: selectedCustomer || null,
        order_number: orderNumber,
        transaction_type: transactionType,
        status: transactionType === 'quick_sale' ? 'completed' : 'pending',
        payment_method: payment.method,
        total_amount: round2(subtotal),
        discount_amount: round2(discAmt),
        discount_reason: discount.reason,
        amount_paid: round2(paidAmt),
        deposit_amount: round2(paidAmt),
        notes,
        estimated_completion: estimatedCompletion || null,
        payment_status: balance <= 0 ? 'paid' : paidAmt > 0 ? 'partial' : 'unpaid',
      })
      await Promise.all(cart.map(item => createOrderItem({
        order: oRes.data.id,
        product: item.product.id,
        variant: item.variant ? item.variant.id : null,
        quantity: item.quantity,
        unit_price: item.unit_price,
        override_price: item.override_price || null,
        override_reason: item.override_reason,
        customization_details: item.customization_details,
        customization_price: item.customization_price,
        stock_status_at_sale: item.stock_status,
        services: item.selected_services.map(s => s.id),
      })))
      setSuccess({ orderNumber, total: round2(total).toFixed(2), balance: round2(balance).toFixed(2) })
      setCart([])
      setOrderNumber('ORD-' + Date.now().toString().slice(-6))
      setDiscount({ amount: 0, reason: '' })
      setPayment({ method: 'cash', amount_paid: 0 })
      setNotes('')
    } catch (err) {
      alert('Checkout failed: ' + JSON.stringify(err.response ? err.response.data : err.message))
    }
    setLoading(false)
  }

  if (success) return (
    <div className="flex items-center justify-center h-screen bg-gray-100">
      <div className="bg-white p-8 rounded-2xl shadow-xl text-center w-96">
        <div className="w-14 h-14 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <span className="text-emerald-600 text-2xl">✓</span>
        </div>
        <h2 className="text-xl font-semibold">{transactionType === 'quick_sale' ? 'Sale complete!' : 'Order placed!'}</h2>
        <p className="text-gray-400 text-sm mt-1">Order {success.orderNumber}</p>
        <p className="text-3xl font-bold mt-3">${success.total}</p>
        {parseFloat(success.balance) > 0 && <p className="text-rose-500 text-sm mt-1">Balance due: ${success.balance}</p>}
        <button onClick={() => setSuccess(null)} className="mt-6 w-full bg-indigo-600 text-white py-2.5 rounded-xl text-sm hover:bg-indigo-700">New transaction</button>
      </div>
    </div>
  )

    return (
    <div className="flex h-full bg-gray-50">

      {/* LEFT — product browser */}
      <div className="w-[55%] flex flex-col overflow-hidden border-r border-gray-200 bg-white">

        {/* header */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between gap-4">
          <h1 className="text-base font-semibold text-gray-800">Point of Sale</h1>
          <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
            {[{k:'quick_sale',l:'Quick Sale'},{k:'custom_order',l:'Custom Order'}].map(t => (
              <button key={t.k} onClick={() => { setTransactionType(t.k); setCart([]) }}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${transactionType === t.k ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                {t.l}
              </button>
            ))}
          </div>
          <select value={selectedBranch ? selectedBranch.id : ''}
            onChange={e => setSelectedBranch(branches.find(b => b.id === parseInt(e.target.value)))}
            className="text-xs border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300">
            {branches.map(b => <option key={b.id} value={b.id}>{b.name} — {b.city}</option>)}
          </select>
        </div>

        {/* search */}
        <div className="px-5 py-3 border-b border-gray-100">
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search products..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-gray-50" />
        </div>

        {/* product grid */}
        <div className="flex-1 overflow-y-auto p-5 grid grid-cols-2 gap-3 content-start">
          {filtered.map(product => (
            <div key={product.id} className="bg-white rounded-xl border border-gray-100 p-4 hover:border-indigo-200 hover:shadow-sm transition">
              <div className="flex items-start justify-between mb-2">
                <p className="font-medium text-sm text-gray-800 leading-tight">{product.name}</p>
                <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ml-2 ${product.item_type === 'customizable' ? 'bg-purple-50 text-purple-700' : 'bg-gray-100 text-gray-500'}`}>
                  {product.item_type}
                </span>
              </div>
              <p className="text-base font-bold text-indigo-600 mb-3">${toNum(product.base_price).toFixed(2)}</p>
              {product.variants && product.variants.length > 0 ? (
                <div className="space-y-1.5">
                  {product.variants.map(v => (
                    <button key={v.id} onClick={() => addToCart(product, v)}
                      className={`w-full text-xs px-3 py-2 rounded-lg border flex justify-between items-center transition hover:opacity-90 active:scale-98 ${stockStyles[v.stock_status || 'in_stock']}`}>
                      <span className="font-semibold">{v.size} / {v.color}</span>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${stockDot[v.stock_status || 'in_stock']}`} />
                        <span>{v.available_quantity != null ? v.available_quantity : v.stock_quantity} left</span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <button onClick={() => addToCart(product)}
                  className="w-full bg-indigo-600 text-white text-xs px-3 py-2 rounded-lg hover:bg-indigo-700 transition font-medium">
                  + Add to cart
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* RIGHT — cart */}
      <div className="w-[45%] max-w-[520px] flex flex-col bg-white border-l border-gray-100">

        {/* cart header */}
        <div className="px-5 py-4 border-b border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-800">Cart</h2>
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${transactionType === 'quick_sale' ? 'bg-teal-50 text-teal-700' : 'bg-purple-50 text-purple-700'}`}>
              {transactionType === 'quick_sale' ? 'Quick sale' : 'Custom order'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">Order number</label>
              <input value={orderNumber} onChange={e => setOrderNumber(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">Customer</label>
              <select value={selectedCustomer || ''} onChange={e => setSelectedCustomer(e.target.value || null)}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                <option value="">Walk-in</option>
                {customers.map(c => <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>)}
              </select>
            </div>
          </div>
        </div>

        {/* cart items */}
        <div className="flex-1 min-h-[300px] overflow-y-auto px-4 py-3 space-y-3">
          {cart.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-gray-300">
              <p className="text-sm">Cart is empty</p>
              <p className="text-xs mt-1">Click a product to add it</p>
            </div>
          ) : cart.map(item => {
            const effPrice = (item.override_price !== null && item.override_price !== '') ? toNum(item.override_price) : toNum(item.unit_price)
            const svcTotal = toNum(item.customization_price)
            const lineTotal = (effPrice + svcTotal) * item.quantity
            return (
              <div key={item.key} className="bg-gray-50 rounded-xl border border-gray-100 overflow-hidden min-h-[180px]">

                {/* item header */}
                <div className="px-4 pt-4 pb-2 space-y-1">
                <p className="text-sm font-semibold text-gray-800">{item.product.name}</p>

                {item.variant && (
                    <p className="text-xs text-gray-400">
                    {item.variant.size} / {item.variant.color}
                    </p>
                )}

                <div className="flex justify-between items-center pt-1">
                    <span className="text-xs text-gray-400">Line total</span>
                    <span className="text-sm font-bold text-gray-800">
                    ${lineTotal.toFixed(2)}
                    </span>
                </div>
                </div>

                {/* qty + price row */}
                <div className="flex items-center gap-3 px-3 pb-2">
                  <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden bg-white">
                    <button onClick={() => decQty(item.key)} className="px-2.5 py-1 text-gray-500 hover:bg-gray-100 font-bold text-base">−</button>
                    <input type="number" min="1" value={item.quantity}
                      onChange={e => updateItem(item.key, 'quantity', Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-10 text-center text-sm py-1 border-x border-gray-200 focus:outline-none" />
                    <button onClick={() => incQty(item.key)} className="px-2.5 py-1 text-gray-500 hover:bg-gray-100 font-bold text-base">+</button>
                  </div>
                  <div className="flex-1 text-xs text-gray-500 space-y-1 leading-relaxed">
                    <div className="flex justify-between"><span>Base</span><span className="text-gray-600">${toNum(item.unit_price).toFixed(2)}</span></div>
                    {svcTotal > 0 && <div className="flex justify-between text-purple-500"><span>Services</span><span>+${svcTotal.toFixed(2)}</span></div>}
                    {item.override_price !== null && <div className="flex justify-between text-amber-500"><span>Override</span><span>${toNum(item.override_price).toFixed(2)}</span></div>}
                  </div>
                </div>

                {/* services */}
                {services.length > 0 && (
                  <div className="border-t border-gray-100 px-3 py-2">
                    <p className="text-xs font-medium text-gray-500 mb-1.5">Add customization</p>
                    <div className="flex flex-wrap gap-1.5">
                      {services.map(svc => {
                        const sel = item.selected_services.find(s => s.id === svc.id)
                        return (
                          <button key={svc.id} onClick={() => toggleService(item.key, svc)}
                            className={`text-xs px-2.5 py-1 rounded-full border font-medium transition ${sel ? 'bg-purple-100 border-purple-300 text-purple-700' : 'bg-white border-gray-200 text-gray-500 hover:border-purple-200 hover:text-purple-600'}`}>
                            {sel ? '✓ ' : ''}{svc.name} +${toNum(svc.price).toFixed(2)}
                          </button>
                        )
                      })}
                    </div>
                    {item.selected_services.length > 0 && (
                      <input placeholder="Details e.g. Add nightclub logo on back"
                        value={item.customization_details}
                        onChange={e => updateItem(item.key, 'customization_details', e.target.value)}
                        className="mt-2 w-full border border-purple-200 rounded-lg px-2 py-1.5 text-xs bg-purple-50 focus:outline-none focus:ring-1 focus:ring-purple-300 placeholder-purple-300" />
                    )}
                  </div>
                )}

                {/* override */}
                <div className="border-t border-gray-100 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <label className="text-xs font-medium text-gray-400 shrink-0">Override price</label>
                    <input type="number" placeholder={toNum(item.unit_price).toFixed(2)}
                      value={item.override_price != null ? item.override_price : ''}
                      onChange={e => updateItem(item.key, 'override_price', e.target.value === '' ? null : toNum(e.target.value))}
                      className="flex-1 border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-amber-300" />
                  </div>
                  {item.override_price !== null && (
                    <input placeholder="Reason e.g. Staff discount"
                      value={item.override_reason}
                      onChange={e => updateItem(item.key, 'override_reason', e.target.value)}
                      className="mt-1.5 w-full border border-amber-200 rounded-lg px-2 py-1 text-xs bg-amber-50 focus:outline-none placeholder-amber-300" />
                  )}
                </div>

              </div>
            )
          })}
        </div>

        {/* checkout panel */}
        <div className="border-t border-gray-100 px-4 py-4 space-y-3 bg-white shrink-0">

          {/* discount row */}
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Discount ($)</label>
              <input type="number" min="0" value={discount.amount}
                onChange={e => setDiscount({ ...discount, amount: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-300" />
            </div>
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Reason</label>
              <input value={discount.reason} onChange={e => setDiscount({ ...discount, reason: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-300" />
            </div>
          </div>

          {/* custom order extras */}
          {transactionType === 'custom_order' && (
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">Estimated completion date</label>
              <input type="date" value={estimatedCompletion} onChange={e => setEstimatedCompletion(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-purple-300" />
            </div>
          )}

          {/* notes */}
          <div>
            <label className="text-xs font-medium text-gray-500 mb-1 block">Notes</label>
            <textarea rows={2} value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="Any special instructions..."
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-300 resize-none" />
          </div>

          {/* payment */}
          <div className="flex gap-2">
            <div className="w-36 shrink-0">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Payment method</label>
              <select value={payment.method} onChange={e => setPayment({ ...payment, method: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none">
                <option value="cash">Cash</option>
                <option value="card">Card</option>
                <option value="mobile_money">Mobile Money</option>
                <option value="bank_transfer">Bank Transfer</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-500 mb-1 block">Amount received ($)</label>
              <input type="number" min="0" value={payment.amount_paid}
                onChange={e => setPayment({ ...payment, amount_paid: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-300" />
            </div>
          </div>

          {/* totals summary */}
          <div className="bg-gray-50 rounded-xl px-4 py-3 space-y-1.5">
            <div className="flex justify-between text-xs text-gray-400">
              <span>Subtotal</span><span>${subtotal.toFixed(2)}</span>
            </div>
            {discAmt > 0 && (
              <div className="flex justify-between text-xs text-emerald-600">
                <span>Discount</span><span>−${discAmt.toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between text-sm font-bold text-gray-800 border-t border-gray-200 pt-1.5">
              <span>Total</span><span>${total.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-xs text-gray-400">
              <span>Paid</span><span>${paidAmt.toFixed(2)}</span>
            </div>
            <div className={`flex justify-between text-base font-bold pt-0.5 ${balance > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
              <span>Balance due</span><span>${balance.toFixed(2)}</span>
            </div>
          </div>

          <button onClick={checkout} disabled={loading || cart.length === 0}
            className={`w-full py-3 rounded-xl text-sm font-semibold transition disabled:opacity-40 disabled:cursor-not-allowed ${transactionType === 'quick_sale' ? 'bg-indigo-600 hover:bg-indigo-700 text-white' : 'bg-purple-600 hover:bg-purple-700 text-white'}`}>
            {loading ? 'Processing...' : transactionType === 'quick_sale' ? 'Complete sale' : 'Place custom order'}
          </button>

        </div>
      </div>
    </div>
  )
}