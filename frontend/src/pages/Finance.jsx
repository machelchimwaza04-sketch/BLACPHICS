import { useEffect, useState } from 'react'
import { useBranch } from '../context/BranchContext'
import {
  getExpenses,
  getRevenue,
  getReports,
  createExpense,
  createRevenue,
  createReport,
} from '../api/api'

export default function Finance() {
  const { branches, selectedBranch, setSelectedBranch, loading: branchLoading } = useBranch()
  const [expenses, setExpenses] = useState([])
  const [revenue, setRevenue] = useState([])
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('expenses')

  const [showExpenseForm, setShowExpenseForm] = useState(false)
  const [showRevenueForm, setShowRevenueForm] = useState(false)
  const [showReportForm, setShowReportForm] = useState(false)

  const [expenseForm, setExpenseForm] = useState({ title: '', description: '', amount: '', date: '' })
  const [revenueForm, setRevenueForm] = useState({ source: 'sales', description: '', amount: '', date: '' })
  const [reportForm, setReportForm] = useState({
    period: 'monthly',
    start_date: '',
    end_date: '',
    total_revenue: '',
    total_expenses: '',
  })

  // Load finances when selectedBranch changes
  useEffect(() => {
    if (!selectedBranch) return
    setLoading(true)
    Promise.all([
      getExpenses(selectedBranch.id),
      getRevenue(selectedBranch.id),
      getReports(selectedBranch.id),
    ])
      .then(([e, r, rep]) => {
        setExpenses(e.data || [])
        setRevenue(r.data || [])
        setReports(rep.data || [])
      })
      .catch(err => console.error('Finance fetch error', err))
      .finally(() => setLoading(false))
  }, [selectedBranch])

  const totalExpenses = expenses.reduce((sum, e) => sum + parseFloat(e.amount || 0), 0)
  const totalRevenue = revenue.reduce((sum, r) => sum + parseFloat(r.amount || 0), 0)
  const netProfit = totalRevenue - totalExpenses

  const handleExpenseSubmit = async (e) => {
    e.preventDefault()
    try {
      const res = await createExpense({ ...expenseForm, branch: selectedBranch.id })
      setExpenses(prev => [...prev, res.data])
      setExpenseForm({ title: '', description: '', amount: '', date: '' })
      setShowExpenseForm(false)
    } catch (err) {
      alert('Failed to create expense')
      console.error(err)
    }
  }

  const handleRevenueSubmit = async (e) => {
    e.preventDefault()
    try {
      const res = await createRevenue({ ...revenueForm, branch: selectedBranch.id })
      setRevenue(prev => [...prev, res.data])
      setRevenueForm({ source: 'sales', description: '', amount: '', date: '' })
      setShowRevenueForm(false)
    } catch (err) {
      alert('Failed to create revenue')
      console.error(err)
    }
  }

  const handleReportSubmit = async (e) => {
    e.preventDefault()
    try {
      const res = await createReport({ ...reportForm, branch: selectedBranch.id })
      setReports(prev => [...prev, res.data])
      setReportForm({
        period: 'monthly',
        start_date: '',
        end_date: '',
        total_revenue: '',
        total_expenses: '',
      })
      setShowReportForm(false)
    } catch (err) {
      alert('Failed to create report')
      console.error(err)
    }
  }

  if (branchLoading) return <div className="p-6">Loading branches...</div>

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Finance</h1>
          <p className="text-gray-500 text-sm">Track expenses, revenue, and profit per branch</p>
        </div>
      </div>

      {/* Branch Selection */}
      <div className="flex gap-4 mt-4">
        {branches.map(b => (
          <button
            key={b.id}
            onClick={() => setSelectedBranch(b)}
            className={`px-4 py-2 rounded-lg text-sm ${
              selectedBranch?.id === b.id
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-700'
            }`}
          >
            {b.name} — {b.city}
          </button>
        ))}
      </div>

      {/* Summary Cards */}
      <div className="flex gap-4 mt-6">
        <div className="flex-1 bg-white p-4 rounded-xl shadow text-center">
          <h3 className="text-sm font-medium text-gray-500">Total Revenue</h3>
          <p className="mt-2 text-xl font-bold">${totalRevenue.toFixed(2)}</p>
        </div>
        <div className="flex-1 bg-white p-4 rounded-xl shadow text-center">
          <h3 className="text-sm font-medium text-gray-500">Total Expenses</h3>
          <p className="mt-2 text-xl font-bold">${totalExpenses.toFixed(2)}</p>
        </div>
        <div className={`flex-1 p-4 rounded-xl shadow text-center ${
          netProfit >= 0 ? 'bg-indigo-50' : 'bg-orange-50'
        }`}>
          <h3 className={`text-sm font-medium ${
            netProfit >= 0 ? 'text-indigo-700' : 'text-orange-700'
          }`}>Net Profit</h3>
          <p className="mt-2 text-xl font-bold">
            ${netProfit.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mt-6">
        {['expenses', 'revenue', 'reports'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              activeTab === tab ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Add Buttons */}
      <div className="mt-4">
        {activeTab === 'expenses' && (
          <button
            onClick={() => setShowExpenseForm(true)}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700"
          >
            + Add expense
          </button>
        )}
        {activeTab === 'revenue' && (
          <button
            onClick={() => setShowRevenueForm(true)}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700"
          >
            + Add revenue
          </button>
        )}
        {activeTab === 'reports' && (
          <button
            onClick={() => setShowReportForm(true)}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700"
          >
            + Generate report
          </button>
        )}
      </div>

      {/* Forms */}
      {showExpenseForm && (
        <FinanceForm
          title="New Expense"
          fields={[
            { label: 'Title', value: expenseForm.title, onChange: (v) => setExpenseForm(f => ({ ...f, title: v })) },
            { label: 'Amount', value: expenseForm.amount, type: 'number', onChange: (v) => setExpenseForm(f => ({ ...f, amount: v })) },
            { label: 'Date', value: expenseForm.date, type: 'date', onChange: (v) => setExpenseForm(f => ({ ...f, date: v })) },
            { label: 'Description', value: expenseForm.description, onChange: (v) => setExpenseForm(f => ({ ...f, description: v })) },
          ]}
          onCancel={() => setShowExpenseForm(false)}
          onSubmit={handleExpenseSubmit}
        />
      )}

      {showRevenueForm && (
        <FinanceForm
          title="New Revenue"
          fields={[
            { label: 'Source', value: revenueForm.source, onChange: (v) => setRevenueForm(f => ({ ...f, source: v })) },
            { label: 'Amount', value: revenueForm.amount, type: 'number', onChange: (v) => setRevenueForm(f => ({ ...f, amount: v })) },
            { label: 'Date', value: revenueForm.date, type: 'date', onChange: (v) => setRevenueForm(f => ({ ...f, date: v })) },
            { label: 'Description', value: revenueForm.description, onChange: (v) => setRevenueForm(f => ({ ...f, description: v })) },
          ]}
          onCancel={() => setShowRevenueForm(false)}
          onSubmit={handleRevenueSubmit}
        />
      )}

      {showReportForm && (
        <FinanceForm
          title="Generate Report"
          fields={[
            { label: 'Period', value: reportForm.period, onChange: (v) => setReportForm(f => ({ ...f, period: v })) },
            { label: 'Start Date', value: reportForm.start_date, type: 'date', onChange: (v) => setReportForm(f => ({ ...f, start_date: v })) },
            { label: 'End Date', value: reportForm.end_date, type: 'date', onChange: (v) => setReportForm(f => ({ ...f, end_date: v })) },
            { label: 'Total Revenue', value: reportForm.total_revenue, type: 'number', onChange: (v) => setReportForm(f => ({ ...f, total_revenue: v })) },
            { label: 'Total Expenses', value: reportForm.total_expenses, type: 'number', onChange: (v) => setReportForm(f => ({ ...f, total_expenses: v })) },
          ]}
          onCancel={() => setShowReportForm(false)}
          onSubmit={handleReportSubmit}
        />
      )}

      {/* Tables */}
      <div className="mt-6">
        {loading ? (
          <div>Loading data...</div>
        ) : activeTab === 'expenses' ? (
          <FinanceTable data={expenses} columns={['Title', 'Description', 'Amount', 'Date']} renderRow={e => (
            <tr key={e.id}>
              <td>{e.title}</td>
              <td>{e.description || '—'}</td>
              <td>${e.amount}</td>
              <td>{new Date(e.date).toLocaleDateString()}</td>
            </tr>
          )} />
        ) : activeTab === 'revenue' ? (
          <FinanceTable data={revenue} columns={['Source', 'Description', 'Amount', 'Date']} renderRow={r => (
            <tr key={r.id}>
              <td>{r.source}</td>
              <td>{r.description || '—'}</td>
              <td>${r.amount}</td>
              <td>{new Date(r.date).toLocaleDateString()}</td>
            </tr>
          )} />
        ) : (
          <FinanceTable data={reports} columns={['Period', 'Start', 'End', 'Revenue', 'Expenses', 'Net Profit', 'Status']} renderRow={r => {
            const net = r.total_revenue - r.total_expenses
            return (
              <tr key={r.id}>
                <td>{r.period}</td>
                <td>{new Date(r.start_date).toLocaleDateString()}</td>
                <td>{new Date(r.end_date).toLocaleDateString()}</td>
                <td>${r.total_revenue}</td>
                <td>${r.total_expenses}</td>
                <td className={net >= 0 ? 'text-indigo-600' : 'text-orange-600'}>${net}</td>
                <td>{net >= 0 ? 'Profitable' : 'Loss'}</td>
              </tr>
            )
          }} />
        )}
      </div>
    </div>
  )
}

// Reusable Form Component
function FinanceForm({ title, fields, onCancel, onSubmit }) {
  return (
    <div className="bg-white p-6 rounded-xl shadow-md mt-4">
      <h2 className="text-lg font-bold mb-4">{title}</h2>
      <form onSubmit={onSubmit} className="grid grid-cols-2 gap-4">
        {fields.map((f, i) => (
          <div key={i}>
            <label className="block text-sm font-medium mb-1">{f.label}</label>
            {f.type === 'textarea' ? (
              <textarea
                value={f.value}
                onChange={e => f.onChange(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              />
            ) : (
              <input
                type={f.type || 'text'}
                value={f.value}
                onChange={e => f.onChange(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              />
            )}
          </div>
        ))}
        <div className="col-span-2 flex justify-end gap-3">
          <button type="button" onClick={onCancel} className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50">Cancel</button>
          <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">Save</button>
        </div>
      </form>
    </div>
  )
}

// Reusable Table Component
function FinanceTable({ data, columns, renderRow }) {
  if (!data.length) return <div className="p-4 text-gray-500">No data found.</div>
  return (
    <table className="w-full text-sm bg-white rounded-xl overflow-hidden">
      <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
        <tr>
          {columns.map(c => <th key={c} className="px-5 py-3 text-left">{c}</th>)}
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-50">
        {data.map(renderRow)}
      </tbody>
    </table>
  )
}