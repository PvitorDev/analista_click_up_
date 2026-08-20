import { cn } from '@/lib/utils'

export function DataTable({
  columns,
  children,
  className,
}: {
  columns: string[]
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('min-w-0 overflow-hidden rounded-lg border border-border', className)}>
      <table className="w-full table-fixed border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-white/[0.02]">
            {columns.map((c) => (
              <th
                key={c}
                className="break-words px-3 py-2 text-left text-xs font-medium uppercase leading-tight tracking-wide text-muted-foreground"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export function Row({ children }: { children: React.ReactNode }) {
  return (
    <tr className="border-b border-border last:border-0 hover:bg-white/[0.02]">
      {children}
    </tr>
  )
}

export function Cell({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <td
      className={cn(
        'min-w-0 break-words px-3 py-2 align-top whitespace-normal text-foreground',
        className,
      )}
    >
      {children}
    </td>
  )
}
