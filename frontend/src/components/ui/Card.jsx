export default function Card({ children, className = '', padding = true }) {
  return (
    <div
      className={`rounded-xl border border-[#e1e3e5] bg-white shadow-[var(--shadow-card)] ${padding ? 'p-5 sm:p-6' : ''} ${className}`}
    >
      {children}
    </div>
  )
}
