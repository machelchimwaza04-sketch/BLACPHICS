import React, { createContext, useState, useEffect } from 'react'
import api, { resetUnauthorizedRedirect } from '../api/api'
import { useNavigate } from 'react-router-dom'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem('accessToken')
    if (token) {
      // Optionally fetch current user
      api.get('/auth/user/').then(res => {
        setUser(res.data)
      }).catch(() => {
        localStorage.removeItem('accessToken')
        localStorage.removeItem('refreshToken')
        setUser(null)
      }).finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (username, password) => {
    const resp = await api.post('/auth/login/', { username, password })
    // flexible handling: token may be in resp.data.access or resp.data.token
    const access = resp.data.access || resp.data.token || resp.data.access_token
    const refresh = resp.data.refresh || resp.data.refresh_token
    if (access) {
      localStorage.setItem('accessToken', access)
    }
    if (refresh) {
      localStorage.setItem('refreshToken', refresh)
    }
    // try to fetch user
    try {
      const me = await api.get('/auth/user/')
      setUser(me.data)
      resetUnauthorizedRedirect()
    } catch (e) {
      setUser(null)
    }
    return resp
  }

  const logout = () => {
    localStorage.removeItem('accessToken')
    localStorage.removeItem('refreshToken')
    setUser(null)
    navigate('/login')
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export default AuthContext
