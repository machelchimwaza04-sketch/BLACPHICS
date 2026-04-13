import axios from 'axios'
import toast from 'react-hot-toast'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const s = err.response?.status
    if (s === 403) toast.error('Access denied for this branch or resource.')
    else if (s && s >= 500) toast.error('Server error. Try again later.')
    return Promise.reject(err)
  }
)

export default api
