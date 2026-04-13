import { useEffect, useState } from 'react'
import {
  getBranches, getPLReport,
  getExpenses, createExpense,
  getExpenseCategories,
  getRevenue, createRevenue,
} from '../api/api'

const PERIODS = [
  { k: 'month', l: 'This month' },
  { k: 'quarter', l: 'This quarter' },
  { k: 'year', l: 'This year' },
  { k: 'all', l: 'All time' },
]

const fmt = (n) => '$' + (Number(n) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const pct = (n) => (Number(n) || 0).toFixed(1) + '%'

const emptyExpense = () => ({ description: '', amount: '', category: '', date: new Date().toISOString().slice(0, 10), branch: '' })
const emptyRevenue = () => ({ description: '', amount: '', source: 'other', date: new Date().toISOString().slice(0, 10), branch: '' })

export default function Finance() {
  const [branches, setBranches] = useState([])
  const [selectedBranch, setSelectedBranch] = useState(null)
  const [period, setPeriod] = useState('month')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('pl')
  const [expenses, setExpenses] = useState([])
  const [revenues, setRevenues] = useState([])
  const [categories, setCategories] = useState([])
  const [showExpenseForm, setShowExpenseForm] = useState(false)
  const [showRevenueForm, setShowRevenueForm] = useState(false)
  const [expenseForm, setExpenseForm] = useState(emptyExpense())
  const [revenueForm, setRevenueForm] = useState(emptyRevenue())

  const toNum = (v) => Number(v) || 0

  useEffect(() => {
    getBranches().then(r => {
      setBranches(r.data)
      if (r.data.length > 0) setSelectedBranch(r.data[0])
    })
    getExpenseCategories().then(r => setCategories(r.data))
  }, [])

  useEffect(() => {
    if (!selectedBranch) return
    setLoading(true)
    Promise.all([
      getPLReport(selectedBranch.id, period),
      getExpenses(selectedBranch.id),
      getRevenue(selectedBranch.id),
    ]).then(([pl, exp, rev]) => {
      setReport(pl.data)
      setExpenses(exp.data)
      setRevenues(rev.data)
    }).finally(() => setLoading(false))
  }, [selectedBranch, period])

  const handleAddExpense = async (e) => {
    e.preventDefault()
    try {
      const res = await createExpense({ ...expenseForm, branch: selectedBranch.id, amount: toNum(expenseForm.amount) })
      setExpenses(prev => [res.data, ...prev])
      setShowExpenseForm(false)
      setExpenseForm(emptyExpense())
      // Refresh report
      getPLReport(selectedBranch.id, period).then(r => setReport(r.data))
    } catch (err) {
      alert('Error: ' + JSON.stringify(err.response?.data))
    }
  }

  const handleAddRevenue = async (e) => {
    e.preventDefault()
    try {
      const res = await createRevenue({ ...revenueForm, branch: selectedBranch.id, amount: toNum(revenueForm.amount) })
      setRevenues(prev => [res.data, ...prev])
      setShowRevenueForm(false)
      setRevenueForm(emptyRevenue())
      getPLReport(selectedBranch.id, period).then(r => setReport(r.data))
    } catch (err) {
      alert('Error: ' + JSON.stringify(err.response?.data))
    }
  }

  // Bar chart helper — simple CSS bars
  const maxTrend = report ? Math.max(...report.trend.map(t => Math.max(t.revenue, t.expenses, 1))) : 1
    return (
    <div className="p-8">

            {/* header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Finance</h1>
          <p className="text-sm text-gray-400 mt-0.5">Profit & Loss, expenses and revenue reporting</p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <div className="flex items-center gap-3">
            <select value={selectedBranch?.id || ''} onChange={e => setSelectedBranch(branches.find(b => b.id === parseInt(e.target.value)))}
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none">
              {branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
              {PERIODS.map(p => (
                <button key={p.k} onClick={() => setPeriod(p.k)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${period === p.k ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                  {p.l}
                </button>
              ))}
            </div>
          </div>
          {/* Export buttons — only show when report is loaded */}
                    {report && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">Export:</span>
              <a
                href={`http://127.0.0.1:8000/api/export/pl/?branch=${selectedBranch?.id}&period=${period}&format=pdf`}
                target="_blank" rel="noreferrer"
                className="flex items-center gap-1.5 text-xs border border-rose-200 text-rose-600 px-3 py-1.5 rounded-lg hover:bg-rose-50 transition font-medium"
              >↓ PDF Report</a>
              <a
                href={`http://127.0.0.1:8000/api/export/pl/?branch=${selectedBranch?.id}&period=${period}&format=excel`}
                target="_blank" rel="noreferrer"
                className="flex items-center gap-1.5 text-xs border border-emerald-200 text-emerald-600 px-3 py-1.5 rounded-lg hover:bg-emerald-50 transition font-medium"
              >↓ Excel Report</a>
              <a
                href={`http://127.0.0.1:8000/api/export/orders/?branch=${selectedBranch?.id}&format=pdf`}
                target="_blank" rel="noreferrer"
                className="flex items-center gap-1.5 text-xs border border-indigo-200 text-indigo-600 px-3 py-1.5 rounded-lg hover:bg-indigo-50 transition font-medium"
              >↓ Orders PDF</a>
              <a
                href={`http://127.0.0.1:8000/api/export/orders/?branch=${selectedBranch?.id}&format=excel`}
                target="_blank" rel="noreferrer"
                className="flex items-center gap-1.5 text-xs border border-blue-200 text-blue-600 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition font-medium"
              >↓ Orders Excel</a>
            </div>
          )}
        </div>
      </div>
      {loading ? (
        <div className="p-8 text-center text-gray-400">Loading report...</div>
      ) : !report ? null : (<>

        {/* P&L summary cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Revenue', value: fmt(report.sales.total_revenue), sub: `${report.sales.order_count} orders`, color: 'text-emerald-600', bg: 'bg-emerald-50', icon: '💰' },
            { label: 'COGS', value: fmt(report.cogs), sub: `Gross margin ${pct(report.gross_margin_pct)}`, color: 'text-rose-600', bg: 'bg-rose-50', icon: '📦' },
            { label: 'Gross Profit', value: fmt(report.gross_profit), sub: report.gross_profit >= 0 ? 'After cost of goods' : '⚠ Negative margin', color: report.gross_profit >= 0 ? 'text-blue-600' : 'text-rose-600', bg: 'bg-blue-50', icon: '📊' },
            { label: 'Net Profit', value: fmt(report.net_profit), sub: `Net margin ${pct(report.net_margin_pct)}`, color: report.net_profit >= 0 ? 'text-indigo-600' : 'text-rose-600', bg: 'bg-indigo-50', icon: report.net_profit >= 0 ? '✅' : '⚠️' },
          ].map((c, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-400 mb-1 uppercase tracking-wide">{c.label}</p>
                <p className={`text-2xl font-bold ${c.color}`}>{c.value}</p>
                <p className="text-xs text-gray-400 mt-1">{c.sub}</p>
              </div>
              <div className={`w-11 h-11 ${c.bg} rounded-xl flex items-center justify-center text-xl shrink-0`}>{c.icon}</div>
            </div>
          ))}
        </div>

        {/* tabs */}
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit mb-5">
          {[
            { k: 'pl', l: 'P&L Report' },
            { k: 'trend', l: 'Trend Chart' },
            { k: 'expenses', l: `Expenses (${expenses.length})` },
            { k: 'revenue', l: `Manual Revenue (${revenues.length})` },
          ].map(t => (
            <button key={t.k} onClick={() => setTab(t.k)}
              className={`px-4 py-1.5 rounded-md text-xs font-medium transition ${tab === t.k ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
              {t.l}
            </button>
          ))}
        </div>

        {/* P&L REPORT TAB */}
        {tab === 'pl' && (
          <div className="grid grid-cols-2 gap-5">
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-50 bg-gray-50">
                <h3 className="text-sm font-semibold text-gray-700">Revenue breakdown</h3>
              </div>
              <div className="px-5 py-4 space-y-2 text-sm">
                <div className="flex justify-between text-gray-500"><span>Gross sales</span><span>{fmt(report.sales.gross_sales)}</span></div>
                <div className="flex justify-between text-rose-500"><span>Discounts</span><span>−{fmt(report.sales.discounts)}</span></div>
                <div className="flex justify-between font-medium text-gray-700 border-t pt-2"><span>Net sales</span><span>{fmt(report.sales.net_sales)}</span></div>
                <div className="flex justify-between text-gray-500"><span>Collected</span><span className="text-emerald-600">{fmt(report.sales.total_collected)}</span></div>
                <div className="flex justify-between text-gray-500"><span>Accounts receivable</span><span className="text-amber-600">{fmt(report.sales.accounts_receivable)}</span></div>
                <div className="flex justify-between text-gray-500"><span>Manual revenue</span><span>{fmt(report.sales.manual_revenue)}</span></div>
                <div className="flex justify-between text-base font-bold text-emerald-600 border-t pt-2"><span>Total revenue</span><span>{fmt(report.sales.total_revenue)}</span></div>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-50 bg-gray-50">
                <h3 className="text-sm font-semibold text-gray-700">Cost & expense breakdown</h3>
              </div>
              <div className="px-5 py-4 space-y-2 text-sm">
                <div className="flex justify-between text-gray-500"><span>COGS</span><span className="text-rose-600">{fmt(report.cogs)}</span></div>
                <div className="flex justify-between font-medium text-gray-700 border-t pt-2"><span>Gross profit</span><span className={report.gross_profit >= 0 ? 'text-blue-600' : 'text-rose-600'}>{fmt(report.gross_profit)} ({pct(report.gross_margin_pct)}){}</span></div>
                <div className="flex justify-between text-gray-500 pt-1"><span>Manual expenses</span><span className="text-rose-500">−{fmt(report.expenses.manual)}</span></div>
                <div className="flex justify-between text-gray-500"><span>Supplier payments</span><span className="text-rose-500">−{fmt(report.expenses.supplier_payments)}</span></div>
                <div className="flex justify-between text-gray-500"><span>Supplier outstanding</span><span className="text-amber-600">{fmt(report.expenses.supplier_outstanding)}</span></div>
                <div className="flex justify-between font-bold text-base border-t pt-2">
                  <span>Net profit</span>
                  <span className={report.net_profit >= 0 ? 'text-indigo-600' : 'text-rose-600'}>{fmt(report.net_profit)}</span>
                </div>
                {report.expenses.by_category.length > 0 && (
                  <div className="pt-2 border-t">
                    <p className="text-xs text-gray-400 mb-2 uppercase tracking-wide">Expenses by category</p>
                    {report.expenses.by_category.map((c, i) => (
                      <div key={i} className="flex justify-between text-xs text-gray-500 py-0.5">
                        <span>{c.category__name || 'Uncategorised'}</span>
                        <span>{fmt(c.total)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TREND CHART TAB */}
        {tab === 'trend' && (
          <div className="bg-white rounded-xl border border-gray-100 p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-6">Revenue vs Expenses — last 6 months</h3>
            <div className="flex items-end gap-4 h-48">
              {report.trend.map((t, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <div className="w-full flex items-end gap-1 h-40">
                    <div className="flex-1 bg-emerald-400 rounded-t-md transition-all"
                      style={{height: maxTrend > 0 ? (t.revenue / maxTrend * 100) + '%' : '2%'}}
                      title={`Revenue: ${fmt(t.revenue)}`} />
                    <div className="flex-1 bg-rose-400 rounded-t-md transition-all"
                      style={{height: maxTrend > 0 ? (t.expenses / maxTrend * 100) + '%' : '2%'}}
                      title={`Expenses: ${fmt(t.expenses)}`} />
                  </div>
                  <p className="text-xs text-gray-400 text-center">{t.month}</p>
                  <p className={`text-xs font-medium ${t.profit >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{fmt(t.profit)}</p>
                </div>
              ))}
            </div>
            <div className="flex gap-4 mt-4 justify-center text-xs text-gray-500">
              <div className="flex items-center gap-1"><span className="w-3 h-3 bg-emerald-400 rounded-sm"></span> Revenue</div>
              <div className="flex items-center gap-1"><span className="w-3 h-3 bg-rose-400 rounded-sm"></span> Expenses</div>
            </div>
          </div>
        )}

        {/* EXPENSES TAB */}
        {tab === 'expenses' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <p className="text-sm text-gray-500">Total: <span className="font-semibold text-rose-600">{fmt(report.expenses.manual)}</span></p>
              <button onClick={() => setShowExpenseForm(true)}
                className="bg-indigo-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-indigo-700">+ Add expense</button>
            </div>
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              {expenses.length === 0 ? <p className="p-8 text-center text-gray-400 text-sm">No expenses recorded</p> : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
                    <tr><th className="px-5 py-3 text-left">Date</th><th className="px-5 py-3 text-left">Description</th><th className="px-5 py-3 text-left">Category</th><th className="px-5 py-3 text-right">Amount</th></tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {expenses.map(e => (
                      <tr key={e.id} className="hover:bg-gray-50">
                        <td className="px-5 py-3 text-gray-400">{e.date}</td>
                        <td className="px-5 py-3 font-medium text-gray-700">{e.description}</td>
                        <td className="px-5 py-3 text-gray-500">{e.category_name || '—'}</td>
                        <td className="px-5 py-3 text-right font-semibold text-rose-600">{fmt(e.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* REVENUE TAB */}
        {tab === 'revenue' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <p className="text-sm text-gray-500">Total: <span className="font-semibold text-emerald-600">{fmt(report.sales.manual_revenue)}</span></p>
              <button onClick={() => setShowRevenueForm(true)}
                className="bg-emerald-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-emerald-700">+ Add revenue</button>
            </div>
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              {revenues.length === 0 ? <p className="p-8 text-center text-gray-400 text-sm">No manual revenue recorded</p> : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
                    <tr><th className="px-5 py-3 text-left">Date</th><th className="px-5 py-3 text-left">Description</th><th className="px-5 py-3 text-left">Source</th><th className="px-5 py-3 text-right">Amount</th></tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {revenues.map(r => (
                      <tr key={r.id} className="hover:bg-gray-50">
                        <td className="px-5 py-3 text-gray-400">{r.date}</td>
                        <td className="px-5 py-3 font-medium text-gray-700">{r.description}</td>
                        <td className="px-5 py-3 text-gray-500">{r.source}</td>
                        <td className="px-5 py-3 text-right font-semibold text-emerald-600">{fmt(r.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

      </>)}

      {/* ADD EXPENSE MODAL */}
      {showExpenseForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">Add expense</h2>
            <form onSubmit={handleAddExpense} className="space-y-3">
              <div><label className="text-xs font-medium text-gray-500 mb-1 block">Description</label>
                <input required value={expenseForm.description} onChange={e => setExpenseForm({...expenseForm, description: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-xs font-medium text-gray-500 mb-1 block">Amount ($)</label>
                  <input required type="number" step="0.01" value={expenseForm.amount} onChange={e => setExpenseForm({...expenseForm, amount: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" /></div>
                <div><label className="text-xs font-medium text-gray-500 mb-1 block">Date</label>
                  <input required type="date" value={expenseForm.date} onChange={e => setExpenseForm({...expenseForm, date: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" /></div>
              </div>
              <div><label className="text-xs font-medium text-gray-500 mb-1 block">Category</label>
                <select value={expenseForm.category} onChange={e => setExpenseForm({...expenseForm, category: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                  <option value="">— Uncategorised —</option>
                  {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select></div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700">Save</button>
                <button type="button" onClick={() => setShowExpenseForm(false)} className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm hover:bg-gray-50">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD REVENUE MODAL */}
      {showRevenueForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">Add manual revenue</h2>
            <form onSubmit={handleAddRevenue} className="space-y-3">
              <div><label className="text-xs font-medium text-gray-500 mb-1 block">Description</label>
                <input required value={revenueForm.description} onChange={e => setRevenueForm({...revenueForm, description: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-300" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-xs font-medium text-gray-500 mb-1 block">Amount ($)</label>
                  <input required type="number" step="0.01" value={revenueForm.amount} onChange={e => setRevenueForm({...revenueForm, amount: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" /></div>
                <div><label className="text-xs font-medium text-gray-500 mb-1 block">Date</label>
                  <input required type="date" value={revenueForm.date} onChange={e => setRevenueForm({...revenueForm, date: e.target.value})}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" /></div>
              </div>
              <div><label className="text-xs font-medium text-gray-500 mb-1 block">Source</label>
                <select value={revenueForm.source} onChange={e => setRevenueForm({...revenueForm, source: e.target.value})}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                  <option value="other">Other</option>
                  <option value="sale">Sale</option>
                  <option value="refund">Refund received</option>
                  <option value="investment">Investment</option>
                  <option value="grant">Grant</option>
                </select></div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 bg-emerald-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-emerald-700">Save</button>
                <button type="button" onClick={() => setShowRevenueForm(false)} className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl text-sm hover:bg-gray-50">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}