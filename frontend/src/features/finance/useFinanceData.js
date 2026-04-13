import { useEffect, useState } from 'react'
import {
  getBranches,
  getPLReport,
  getExpenses,
  getExpenseCategories,
  getRevenue,
} from '../../api/api'

export function useFinanceData(period) {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [expenses, setExpenses] = useState([])
  const [revenues, setRevenues] = useState([])
  const [categories, setCategories] = useState([])

  useEffect(() => {
    getBranches().then((r) => {
      setBranches(r.data)
      if (r.data.length > 0) setSelectedBranch(r.data[0])
    })
    getExpenseCategories().then((r) => setCategories(r.data))
  }, [])

  useEffect(() => {
    if (!selectedBranch) return
    setLoading(true)
    Promise.all([
      getPLReport(selectedBranch.id, period),
      getExpenses(selectedBranch.id),
      getRevenue(selectedBranch.id),
    ])
      .then(([pl, exp, rev]) => {
        setReport(pl.data)
        setExpenses(exp.data)
        setRevenues(rev.data)
      })
      .finally(() => setLoading(false))
  }, [selectedBranch, period])

  return {
    branches,
    selectedBranch,
    setSelectedBranch,
    report,
    setReport,
    loading,
    expenses,
    setExpenses,
    revenues,
    setRevenues,
    categories,
  }
}
