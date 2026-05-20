export default function PageHeader({ title, description, actions, children }) {
  return (
    <div className="mb-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#202223] sm:text-[1.75rem]">
            {title}
          </h1>
          {description && (
            <p className="mt-1 text-sm text-[#6d7175] max-w-2xl">{description}</p>
          )}
        </div>
        {(actions || children) && (
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {actions}
            {children}
          </div>
        )}
      </div>
    </div>
  )
}
