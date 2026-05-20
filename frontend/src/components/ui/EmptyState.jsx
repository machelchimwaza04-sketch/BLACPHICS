export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[#c9cccf] bg-white py-16 px-6 text-center">
      {Icon && (
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#f1f2f4] text-[#6d7175]">
          <Icon size={28} strokeWidth={1.5} />
        </div>
      )}
      <h3 className="text-base font-semibold text-[#202223]">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-[#6d7175]">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
