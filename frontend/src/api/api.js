import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Helper — always returns a plain array regardless of response shape
const list = (res) => Array.isArray(res.data) ? res.data : (res.data.results ?? [])
const wrap = (promise) => promise.then(res => ({ ...res, data: list(res) }))

// Branches
export const getBranches = () => wrap(api.get('/branches/'))
export const getBranch = (id) => api.get(`/branches/${id}/`)
export const createBranch = (data) => api.post('/branches/', data)
export const updateBranch = (id, data) => api.put(`/branches/${id}/`, data)
export const deleteBranch = (id) => api.delete(`/branches/${id}/`)

// Products
export const getProducts = (branchId) => wrap(api.get('/products/', { params: { branch: branchId } }))
export const getProduct = (id) => api.get(`/products/${id}/`)
export const createProduct = (data) => api.post('/products/', data)
export const updateProduct = (id, data) => api.put(`/products/${id}/`, data)
export const deleteProduct = (id) => api.delete(`/products/${id}/`)
export const getCategories = () => wrap(api.get('/categories/'))
export const getVariants = () => wrap(api.get('/variants/'))
export const createVariant = (data) => api.post('/variants/', data)
export const deleteVariant = (id) => {return axios.delete(`/api/variants/${id}/`)}
export const getCustomizationServices = () => wrap(api.get('/customization-services/'))
export const updateVariant = async (variantId, data) => {
  return await axios.put(`/api/variants/${variantId}/`, data);
}

// Customers
export const getCustomers = (branchId) => wrap(api.get('/customers/', { params: { branch: branchId } }))
export const getCustomer = (id) => api.get(`/customers/${id}/`)
export const createCustomer = (data) => api.post('/customers/', data)
export const updateCustomer = (id, data) => api.put(`/customers/${id}/`, data)
export const deleteCustomer = (id) => api.delete(`/customers/${id}/`)

// Orders
export const getOrders = (branchId) => wrap(api.get('/orders/', { params: { branch: branchId } }))
export const getOrder = (id) => api.get(`/orders/${id}/`)
export const createOrder = (data) => api.post('/orders/', data)
export const updateOrder = (id, data) => api.put(`/orders/${id}/`, data)
export const deleteOrder = (id) => api.delete(`/orders/${id}/`)
export const createOrderItem = (data) => api.post('/order-items/', data)

// Suppliers
export const getSuppliers = () => wrap(api.get('/suppliers/'))
export const getSupplier = (id) => api.get(`/suppliers/${id}/`)
export const createSupplier = (data) => api.post('/suppliers/', data)
export const updateSupplier = (id, data) => api.put(`/suppliers/${id}/`, data)
export const getPurchases = (branchId) => wrap(api.get('/purchases/', { params: { branch: branchId } }))
export const createPurchase = (data) => api.post('/purchases/', data)
export const updatePurchase = (id, data) => api.put(`/purchases/${id}/`, data)

// Finance
export const getExpenses = (branchId) => wrap(api.get('/expenses/', { params: { branch: branchId } }))
export const createExpense = (data) => api.post('/expenses/', data)
export const getRevenue = (branchId) => wrap(api.get('/revenue/', { params: { branch: branchId } }))
export const createRevenue = (data) => api.post('/revenue/', data)
export const getReports = (branchId) => wrap(api.get('/reports/', { params: { branch: branchId } }))
export const createReport = (data) => api.post('/reports/', data)

export default api