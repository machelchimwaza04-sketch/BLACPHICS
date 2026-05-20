export default function PageContent({ children, className = '', fullBleed = false }) {
  if (fullBleed) return children
  return (
    <div className={`flex-1 overflow-auto p-5 sm:p-6 lg:p-8 ${className}`}>
      <div className="mx-auto max-w-[1400px]">{children}</div>
    </div>
  )
}
