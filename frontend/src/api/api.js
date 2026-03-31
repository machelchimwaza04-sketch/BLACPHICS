import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Branches
export const getBranches = () => api.get('/branches/')
export const getBranch = (id) => api.get(`/branches/${id}/`)
export const createBranch = (data) => api.post('/branches/', data)
export const updateBranch = (id, data) => api.put(`/branches/${id}/`, data)
export const deleteBranch = (id) => api.delete(`/branches/${id}/`)

// Products
export const getProducts = (branchId) => api.get('/products/', { params: { branch: branchId } })
export const getProduct = (id) => api.get(`/products/${id}/`)
export const createProduct = (data) => api.post('/products/', data)
export const updateProduct = (id, data) => api.put(`/products/${id}/`, data)
export const deleteProduct = (id) => api.delete(`/products/${id}/`)
export const getCategories = () => api.get('/categories/')
export const getVariants = () => api.get('/variants/')

// Customers
export const getCustomers = (branchId) => api.get('/customers/', { params: { branch: branchId } })
export const getCustomer = (id) => api.get(`/customers/${id}/`)
export const createCustomer = (data) => api.post('/customers/', data)
export const updateCustomer = (id, data) => api.put(`/customers/${id}/`, data)
export const deleteCustomer = (id) => api.delete(`/customers/${id}/`)

// Orders
export const getOrders = (branchId) => api.get('/orders/', { params: { branch: branchId } })
export const getOrder = (id) => api.get(`/orders/${id}/`)
export const createOrder = (data) => api.post('/orders/', data)
export const updateOrder = (id, data) => api.put(`/orders/${id}/`, data)
export const deleteOrder = (id) => api.delete(`/orders/${id}/`)
export const createOrderItem = (data) => api.post('/order-items/', data)

// Suppliers
export const getSuppliers = () => api.get('/suppliers/')
export const getSupplier = (id) => api.get(`/suppliers/${id}/`)
export const createSupplier = (data) => api.post('/suppliers/', data)
export const updateSupplier = (id, data) => api.put(`/suppliers/${id}/`, data)
export const getPurchases = (branchId) => api.get('/purchases/', { params: { branch: branchId } })
export const createPurchase = (data) => api.post('/purchases/', data)
export const updatePurchase = (id, data) => api.put(`/purchases/${id}/`, data)

// Finance
export const getExpenses = (branchId) => api.get('/expenses/', { params: { branch: branchId } })
export const createExpense = (data) => api.post('/expenses/', data)
export const getRevenue = (branchId) => api.get('/revenue/', { params: { branch: branchId } })
export const createRevenue = (data) => api.post('/revenue/', data)
export const getReports = (branchId) => api.get('/reports/', { params: { branch: branchId } })
export const createReport = (data) => api.post('/reports/', data)

export default api