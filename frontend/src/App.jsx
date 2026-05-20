import { Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Products from './pages/Products'
import Customers from './pages/Customers'
import Orders from './pages/Orders'
import Suppliers from './pages/Suppliers'
import Finance from './pages/Finance'
import POS from './pages/POS'
import Alerts from './pages/Alerts'
import Login from './pages/Login'
import useAuth from './auth/useAuth'
import { BranchProvider } from './context/BranchContext'
import AppShell from './components/layout/AppShell'
import PageContent from './components/layout/PageContent'

function LoadingScreen() {
  return (
    <div className="flex h-screen items-center justify-center bg-[#f6f6f7]">
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-[#e1e3e5] border-t-[#008060]" />
        <p className="text-sm text-[#6d7175]">Loading Blacphics…</p>
      </div>
    </div>
  )
}

export default function App() {
  const { user, loading } = useAuth()

  if (loading) return <LoadingScreen />

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <BranchProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<PageContent><Dashboard /></PageContent>} />
          <Route path="/products" element={<PageContent><Products /></PageContent>} />
          <Route path="/customers" element={<PageContent><Customers /></PageContent>} />
          <Route path="/orders" element={<PageContent><Orders /></PageContent>} />
          <Route path="/suppliers" element={<PageContent><Suppliers /></PageContent>} />
          <Route path="/finance" element={<PageContent><Finance /></PageContent>} />
          <Route path="/alerts" element={<PageContent><Alerts /></PageContent>} />
          <Route path="/pos" element={<PageContent fullBleed><POS /></PageContent>} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BranchProvider>
  )
}
