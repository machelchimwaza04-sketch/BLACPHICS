import { useBranch } from '../../context/BranchContext'
import { ChevronDown, Store } from 'lucide-react'

export default function BranchSelect({ className = '' }) {
  const { branches, selectedBranch, setSelectedBranch } = useBranch()

  if (!branches.length) {
    return (
      <span className={`text-sm text-[#6d7175] ${className}`}>No branches</span>
    )
  }

  return (
    <div className={`relative inline-flex items-center ${className}`}>
      <Store size={16} className="absolute left-3 text-[#6d7175] pointer-events-none" />
      <select
        value={selectedBranch?.id || ''}
        onChange={(e) => {
          const branch = branches.find((b) => b.id === Number(e.target.value))
          if (branch) setSelectedBranch(branch)
        }}
        className="appearance-none rounded-lg border border-[#c9cccf] bg-white py-2 pl-9 pr-9 text-sm font-medium text-[#202223] shadow-sm hover:border-[#aeb4b9] focus:border-[#008060] focus:outline-none focus:ring-2 focus:ring-[#008060]/20 min-w-[180px]"
      >
        {branches.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}{b.city ? ` · ${b.city}` : ''}
          </option>
        ))}
      </select>
      <ChevronDown size={16} className="absolute right-3 text-[#6d7175] pointer-events-none" />
    </div>
  )
}
