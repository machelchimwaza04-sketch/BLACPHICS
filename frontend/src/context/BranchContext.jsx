import { createContext, useContext, useEffect, useState } from 'react'
import { getBranches } from '../api/api'

const BranchContext = createContext()

export function BranchProvider({ children }) {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await getBranches()

        // ✅ SAFE parsing (important)
        const branchList = Array.isArray(res.data)
          ? res.data
          : res.data?.results || []

        setBranches(branchList)

        // ✅ Restore from localStorage (UX upgrade)
        const savedBranch = localStorage.getItem('selectedBranch')

        if (savedBranch) {
          const parsed = JSON.parse(savedBranch)
          const exists = branchList.find(b => b.id === parsed.id)

          if (exists) {
            setSelectedBranch(exists)
          } else if (branchList.length) {
            setSelectedBranch(branchList[0])
          }
        } else if (branchList.length) {
          setSelectedBranch(branchList[0])
        }

      } catch (err) {
        console.error('Failed to load branches', err)
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  // ✅ Persist branch (pro-level UX)
  useEffect(() => {
    if (selectedBranch) {
      localStorage.setItem(
        'selectedBranch',
        JSON.stringify(selectedBranch)
      )
    }
  }, [selectedBranch])

  return (
    <BranchContext.Provider
      value={{
        branches,
        selectedBranch,
        setSelectedBranch,
        loading,
      }}
    >
      {children}
    </BranchContext.Provider>
  )
}

// ✅ SAFE HOOK (critical fix)
export function useBranch() {
  const context = useContext(BranchContext)

  if (!context) {
    throw new Error('useBranch must be used inside BranchProvider')
  }

  return context
}