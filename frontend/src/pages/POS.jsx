import { useEffect, useState, useMemo } from 'react'
import {
  getBranches,
  getProducts,
  getCustomers,
  createOrder
} from '../api/api'

const stockStyles = {
  in_stock: 'bg-emerald-100 text-emerald-700',
  low_stock: 'bg-yellow-100 text-yellow-700',
  out_of_stock: 'bg-rose-100 text-rose-700',
}

export default function POS() {

  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)

  const [products, setProducts] = useState([])
  const [customers, setCustomers] = useState([])

  const [search, setSearch] = useState('')
  const [cart, setCart] = useState([])

  const [transactionType, setTransactionType] = useState('quick_sale')
  const [selectedCustomer, setSelectedCustomer] = useState(null)

  const [payment, setPayment] = useState({ method: 'cash', amount_paid: 0 })
  const [discount, setDiscount] = useState({ amount: 0, reason: '' })

  const [loading, setLoading] = useState(false)

  // =========================
  // LOAD DATA
  // =========================
  useEffect(() => {
    getBranches().then(res => {
      setBranches(res.data)
      if (res.data.length > 0) setSelectedBranch(res.data[0])
    })
  }, [])

  useEffect(() => {
    if (!selectedBranch) return

    Promise.all([
      getProducts(selectedBranch.id),
      getCustomers(selectedBranch.id)
    ]).then(([p, c]) => {
      setProducts(p.data)
      setCustomers(c.data)
    })

    setCart([])
  }, [selectedBranch])

  // =========================
  // FILTERED PRODUCTS
  // =========================
  const filteredProducts = useMemo(() => {
    return products.filter(p =>
      p.name.toLowerCase().includes(search.toLowerCase())
    )
  }, [products, search])

  // =========================
  // CART
  // =========================
    const addToCart = (product, variant = null) => {

  if (transactionType === 'quick_sale') {
    const status = variant ? variant.stock_status : 'in_stock'
    if (status === 'out_of_stock') {
      alert('This item is out of stock. Switch to Custom Order to add it.')
      return
    }
  }

  const key = variant ? `${product.id}-${variant.id}` : `${product.id}`
  const existing = cart.find(i => i.key === key)

  // 🔒 SAFE NUMBER PARSING (handles strings/null/undefined)
  const basePrice = Number(product.base_price) || 0
  const extraPrice = variant ? Number(variant.extra_price) || 0 : 0
  const customPrice = Number(product.customization_price) || 0

  if (existing) {
    setCart(cart.map(i =>
      i.key === key
        ? { ...i, quantity: (Number(i.quantity) || 0) + 1 }
        : i
    ))
  } else {
    setCart([
      ...cart,
      {
        key,
        product,
        variant,
        quantity: 1,
        unit_price: basePrice + extraPrice,
        override_price: null,
        override_reason: '',
        customization_details: '',
        customization_price: customPrice,
        stock_status: variant
          ? (variant.stock_status || 'in_stock')
          : 'in_stock',
      }
    ])
  }
}
  const updateQty = (key, qty) => {
    if (qty <= 0) return
    setCart(cart.map(i => i.key === key ? { ...i, quantity: qty } : i))
  }

  const removeItem = (key) => {
    setCart(cart.filter(i => i.key !== key))
  }

  // =========================
  // TOTALS
  // =========================
    const subtotal = cart.reduce((sum, i) => {

  const price =
    i.override_price !== null && i.override_price !== ''
      ? Number(i.override_price) || 0
      : Number(i.unit_price) || 0

  const customization = Number(i.customization_price) || 0
  const qty = Number(i.quantity) || 1

  return sum + (price + customization) * qty

}, 0)

const discountAmount = Number(discount.amount) || 0
const paidAmount = Number(payment.amount_paid) || 0

const total = subtotal - discountAmount
const balance = total - paidAmount

  // =========================
  // CHECKOUT
  // =========================
  const handleCheckout = async () => {
    if (!cart.length) return alert('Cart is empty')

    setLoading(true)

    try {
      await createOrder({
        branch: selectedBranch.id,
        customer: selectedCustomer,
        transaction_type: transactionType,
        status: transactionType === 'quick_sale' ? 'completed' : 'pending',
        payment_method: payment.method,
        discount_amount: discount.amount,
        discount_reason: discount.reason,
        amount_paid: payment.amount_paid,
        deposit_amount: payment.amount_paid,
        items: cart.map(i => ({
          product: i.product.id,
          variant: i.variant.id,
          quantity: i.quantity,
          unit_price: i.unit_price
        }))
      })

      setCart([])
      setPayment({ method: 'cash', amount_paid: 0 })
      setDiscount({ amount: 0, reason: '' })

      alert('Transaction successful')

    } catch (err) {
      alert('Error processing order')
    }

    setLoading(false)
  }

  return (
    <div className="flex h-screen bg-gray-100">

      {/* LEFT PANEL */}
      <div className="w-2/3 flex flex-col">

        {/* HEADER */}
        <div className="p-4 bg-white shadow-sm flex justify-between items-center">
          <h1 className="text-lg font-semibold">Point of Sale</h1>

          <div className="flex gap-2">
            {['quick_sale', 'custom_order'].map(type => (
              <button
                key={type}
                onClick={() => { setTransactionType(type); setCart([]) }}
                className={`px-3 py-1.5 rounded-md text-sm ${
                  transactionType === type
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-200'
                }`}
              >
                {type === 'quick_sale' ? 'Quick Sale' : 'Custom Order'}
              </button>
            ))}
          </div>
        </div>

        {/* SEARCH */}
        <div className="p-4">
          <input
            placeholder="Search products..."
            className="w-full border px-3 py-2 rounded-lg"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* PRODUCT GRID */}
        <div className="grid grid-cols-3 gap-4 p-4 overflow-y-auto">

          {filteredProducts.map(product => (
            <div key={product.id} className="bg-white p-3 rounded-xl shadow-sm hover:shadow-md transition">

              <div className="font-medium text-sm">{product.name}</div>

              <div className="mt-2 space-y-1">
                {product.variants.map(v => (
                  <button
                    key={v.id}
                    onClick={() => addToCart(product, v)}
                    className={`w-full text-xs px-2 py-1 rounded-md flex justify-between ${stockStyles[v.stock_status]}`}
                  >
                    <span>{v.size} / {v.color}</span>
                    <span>{v.available_quantity}</span>
                  </button>
                ))}
              </div>

            </div>
          ))}

        </div>

      </div>

      {/* RIGHT PANEL */}
      <div className="w-1/3 bg-white shadow-lg flex flex-col">

        <div className="p-4 border-b">
          <h2 className="font-semibold">Cart</h2>
        </div>

        {/* CART LIST */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">

          {cart.length === 0 && (
            <div className="text-sm text-gray-400">No items</div>
          )}

          {cart.map(item => (
            <div key={item.key} className="border rounded-lg p-2">

              <div className="flex justify-between text-sm">
                <span>{item.product.name}</span>
                <button onClick={() => removeItem(item.key)}>✕</button>
              </div>

              <div className="text-xs text-gray-500">
                {item.variant.size} / {item.variant.color}
              </div>

              <input
                type="number"
                value={item.quantity}
                onChange={(e) => updateQty(item.key, parseInt(e.target.value))}
                className="w-full mt-1 border rounded px-2 py-1 text-sm"
              />

            </div>
          ))}

        </div>

        {/* FOOTER */}
        <div className="p-4 border-t space-y-2 text-sm">

          <div className="flex justify-between">
            <span>Subtotal</span>
            <span>${subtotal.toFixed(2)}</span>
          </div>

          <div className="flex justify-between font-semibold">
            <span>Total</span>
            <span>${total.toFixed(2)}</span>
          </div>

          <input
            type="number"
            placeholder="Amount paid"
            className="w-full border px-2 py-1 rounded"
            onChange={(e) => setPayment({
              ...payment,
              amount_paid: parseFloat(e.target.value) || 0
            })}
          />

          <div className={`flex justify-between font-medium ${balance > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
            <span>Balance</span>
            <span>${balance.toFixed(2)}</span>
          </div>

          <button
            onClick={handleCheckout}
            className="w-full mt-2 bg-indigo-600 text-white py-2 rounded-lg hover:bg-indigo-700 transition"
          >
            {loading ? 'Processing...' : 'Checkout'}
          </button>

        </div>

      </div>

    </div>
  )
}