export default function StatCard({ label, value, icon: Icon, trend, accent = 'brand' }) {
  const accents = {
    brand: 'bg-[#008060]/10 text-[#008060]',
    blue: 'bg-blue-50 text-blue-600',
    amber: 'bg-amber-50 text-amber-600',
    rose: 'bg-rose-50 text-rose-600',
  }

  return (
    <div className="rounded-xl border border-[#e1e3e5] bg-white p-5 shadow-[var(--shadow-card)] transition hover:shadow-[var(--shadow-elevated)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[#6d7175]">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-[#202223] tabular-nums">
            {value}
          </p>
          {trend != null && (
            <p className="mt-1 text-xs text-[#6d7175]">{trend}</p>
          )}
        </div>
        {Icon && (
          <div className={`flex h-11 w-11 items-center justify-center rounded-lg ${accents[accent]}`}>
            <Icon size={22} strokeWidth={1.75} />
          </div>
        )}
      </div>
    </div>
  )
}
