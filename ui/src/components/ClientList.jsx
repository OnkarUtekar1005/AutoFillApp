import { Building2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { statusMeta } from '@/lib/status'
import { Card, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'

export default function ClientList({ filings, selected, onSelect }) {
  const counts = filings.reduce((acc, f) => {
    acc[f.status] = (acc[f.status] || 0) + 1
    return acc
  }, {})

  return (
    <Card className="py-0 overflow-hidden">
      <CardHeader className="border-b py-3.5 px-4">
        <CardTitle>Clients ({filings.length})</CardTitle>
        <CardAction className="flex gap-1.5">
          {Object.entries(counts).map(([status, n]) => {
            const s = statusMeta(status)
            return (
              <Badge key={status} variant="outline" className={cn('gap-1', s.badge)}>
                <span className={cn('size-1.5 rounded-full', s.dot)} />
                {n}
              </Badge>
            )
          })}
        </CardAction>
      </CardHeader>

      <ScrollArea className="h-[440px]">
        <div className="divide-y">
          {filings.map((f, i) => {
            const s = statusMeta(f.status)
            const Icon = s.icon
            const isSelected = selected === i
            return (
              <button
                key={i}
                onClick={() => onSelect(i)}
                className={cn(
                  'w-full text-left px-4 py-3 flex items-center gap-3 transition-colors',
                  isSelected ? 'bg-accent' : 'hover:bg-accent/50'
                )}
              >
                <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <Building2 className="size-4 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm truncate">{f.client_name}</p>
                  <p className="text-xs text-muted-foreground font-mono truncate">
                    {f.cin || 'CIN not found'} · {f.period}
                  </p>
                </div>
                <Icon className={cn('size-4 shrink-0', s.iconText)} />
              </button>
            )
          })}
        </div>
      </ScrollArea>
    </Card>
  )
}
