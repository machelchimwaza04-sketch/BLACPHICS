const styles = {
  default: 'bg-[#f1f2f4] text-[#202223]',
  success: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-800',
  danger: 'bg-rose-50 text-rose-700',
  info: 'bg-blue-50 text-blue-700',
  brand: 'bg-[#008060]/10 text-[#008060]',
}

export default function Badge({ children, tone = 'default', className = '' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[tone]} ${className}`}
    >
      {children}
    </span>
  )
}
