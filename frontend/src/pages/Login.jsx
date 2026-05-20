import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Lock, ArrowRight } from 'lucide-react'
import useAuth from '../auth/useAuth'
import { resetUnauthorizedRedirect } from '../api/api'
import Button from '../components/ui/Button'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    resetUnauthorizedRedirect()
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/')
    } catch {
      setError('Invalid username or password. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Brand panel */}
      <div className="hidden w-1/2 flex-col justify-between bg-[#202223] p-12 text-white lg:flex">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#008060]">
            <Sparkles size={22} />
          </div>
          <span className="text-xl font-semibold tracking-tight">Blacphics</span>
        </div>
        <div>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">
            Run your store with confidence
          </h1>
          <p className="mt-4 max-w-md text-lg text-gray-400 leading-relaxed">
            Point of sale, inventory, orders, and finance — unified in one professional workspace built for multi-branch teams.
          </p>
        </div>
        <p className="text-sm text-gray-500">© Blacphics Business Manager</p>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 flex-col items-center justify-center bg-[#f6f6f7] p-6 sm:p-10">
        <div className="w-full max-w-[400px]">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#008060] text-white">
              <Sparkles size={20} />
            </div>
            <span className="text-lg font-semibold text-[#202223]">Blacphics</span>
          </div>

          <div className="rounded-xl border border-[#e1e3e5] bg-white p-8 shadow-[var(--shadow-card)]">
            <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-[#008060]/10 text-[#008060]">
              <Lock size={22} />
            </div>
            <h2 className="text-xl font-semibold text-[#202223]">Sign in to your store</h2>
            <p className="mt-1 text-sm text-[#6d7175]">Enter your staff credentials to continue</p>

            <form onSubmit={submit} className="mt-6 space-y-4">
              {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {error}
                </div>
              )}
              <label className="block">
                <span className="text-sm font-medium text-[#202223]">Username</span>
                <input
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-[#c9cccf] px-3 py-2.5 text-sm focus:border-[#008060] focus:outline-none focus:ring-2 focus:ring-[#008060]/20"
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-[#202223]">Password</span>
                <input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-[#c9cccf] px-3 py-2.5 text-sm focus:border-[#008060] focus:outline-none focus:ring-2 focus:ring-[#008060]/20"
                  required
                />
              </label>
              <Button
                type="submit"
                size="lg"
                className="w-full mt-2"
                disabled={submitting}
              >
                {submitting ? 'Signing in…' : (
                  <>
                    Sign in
                    <ArrowRight size={16} />
                  </>
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
