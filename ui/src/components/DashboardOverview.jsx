import { useMemo, useState } from 'react'
import {
  Users, CheckCircle2, AlertTriangle, FileWarning, Database,
  Search, ArrowUpRight, Paperclip, Pencil, Trash2, MonitorPlay, CircleDashed,
  Zap, Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { statusMeta } from '@/lib/status'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const STAT_TONE = {
  slate: 'text-foreground',
  emerald: 'text-emerald-600 dark:text-emerald-400',
  red: 'text-red-600 dark:text-red-400',
  amber: 'text-amber-600 dark:text-amber-400',
  violet: 'text-violet-600 dark:text-violet-400',
}

function StatTile({ icon: Icon, label, value, sub, tone = 'slate', active, onClick, clickable }) {
  return (
    <Card
      onClick={onClick}
      className={cn('gap-0 transition-colors', clickable && 'cursor-pointer hover:bg-accent/40', active && 'ring-2 ring-primary')}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-muted-foreground">{label}</span>
          <Icon className={cn('size-4', STAT_TONE[tone])} />
        </div>
        <p className={cn('font-heading text-3xl font-semibold leading-none', STAT_TONE[tone])}>{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-1.5">{sub}</p>}
      </CardContent>
    </Card>
  )
}

/**
 * rows: [{ client, result }]  — registry client merged with its extraction
 * result (result may be null = not yet extracted).
 */
export default function DashboardOverview({ rows, extractingId, onOpenClient, onExtractClient, onEditClient, onRemoveClient, onFileClient }) {
  const [filter, setFilter] = useState(null)
  const [query, setQuery] = useState('')

  const stats = useMemo(() => {
    const s = { total: rows.length, ready: 0, attention: 0, missingAtt: 0, fields: 0, mandatoryMissing: 0 }
    for (const { result } of rows) {
      const st = result?.status
      if (st === 'Ready') s.ready++
      else if (st === 'Missing Attachments') s.missingAtt++
      else if (st) s.attention++
      s.fields += result?.total_fields_extracted || 0
      s.mandatoryMissing += result?.validation?.missing_mandatory?.length || 0
    }
    return s
  }, [rows])

  const visible = useMemo(() => {
    return rows
      .filter(({ result }) => !filter || result?.status === filter)
      .filter(({ client }) => {
        if (!query) return true
        const t = query.toLowerCase()
        return client.name.toLowerCase().includes(t) || (client.cin || '').toLowerCase().includes(t)
      })
  }, [rows, filter, query])

  const readyPct = stats.total ? Math.round((stats.ready / stats.total) * 100) : 0

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatTile icon={Users} label="Total Clients" value={stats.total}
          clickable active={filter === null} onClick={() => setFilter(null)} />
        <StatTile icon={CheckCircle2} label="Ready to File" value={stats.ready} sub={`${readyPct}% of portfolio`} tone="emerald"
          clickable active={filter === 'Ready'} onClick={() => setFilter(filter === 'Ready' ? null : 'Ready')} />
        <StatTile icon={AlertTriangle} label="Needs Attention" value={stats.attention} sub="Missing / failed checks" tone="red"
          clickable active={filter === 'Needs Attention'} onClick={() => setFilter(filter === 'Needs Attention' ? null : 'Needs Attention')} />
        <StatTile icon={FileWarning} label="Missing Attachments" value={stats.missingAtt} sub="Fields OK, no files" tone="amber"
          clickable active={filter === 'Missing Attachments'} onClick={() => setFilter(filter === 'Missing Attachments' ? null : 'Missing Attachments')} />
        <StatTile icon={Database} label="Fields Extracted" value={stats.fields} sub={`${stats.mandatoryMissing} mandatory missing`} tone="violet" />
      </div>

      <Card className="py-0 overflow-hidden gap-0">
        <CardHeader className="border-b py-3.5 px-4 flex-row items-center gap-3">
          <CardTitle>
            Clients
            {filter && <Badge variant="secondary" className="ml-2 font-normal">{filter}</Badge>}
          </CardTitle>
          <div className="ml-auto relative w-full max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input placeholder="Search client or CIN..." value={query} onChange={e => setQuery(e.target.value)} className="pl-8 h-9" />
          </div>
        </CardHeader>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Client</TableHead>
              <TableHead>CIN</TableHead>
              <TableHead className="text-center">Fields</TableHead>
              <TableHead className="text-center">Missing</TableHead>
              <TableHead className="text-center">Attach.</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right pr-4">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map(({ client, result }) => {
              const status = result?.status
              const s = statusMeta(status)
              const StatusIcon = s.icon
              const missing = result?.validation?.missing_mandatory?.length ?? null
              const attachments = result?.attachments?.length ?? null
              return (
                <TableRow key={client.id} className="cursor-pointer" onClick={() => onOpenClient(client.id)}>
                  <TableCell className="font-medium">{client.name}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{client.cin || '—'}</TableCell>
                  <TableCell className="text-center tabular-nums">{result?.total_fields_extracted ?? '—'}</TableCell>
                  <TableCell className="text-center tabular-nums">
                    {missing == null ? '—' : missing > 0
                      ? <span className="text-red-600 dark:text-red-400 font-medium">{missing}</span>
                      : <span className="text-emerald-600 dark:text-emerald-400">0</span>}
                  </TableCell>
                  <TableCell className="text-center tabular-nums">
                    {attachments == null ? '—' : (
                      <span className={cn('inline-flex items-center gap-1', attachments === 0 && 'text-amber-600 dark:text-amber-400')}>
                        <Paperclip className="size-3" />{attachments}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {status ? (
                      <Badge variant="outline" className={cn('gap-1', s.badge)}>
                        <StatusIcon className="size-3" />{status}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="gap-1 text-muted-foreground">
                        <CircleDashed className="size-3" />Not extracted
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right pr-2" onClick={e => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-0.5">
                      <Button variant="ghost" size="icon" className="size-7" title="Extract this client (writes its Excel)"
                        disabled={extractingId === client.id} onClick={() => onExtractClient(client)}>
                        {extractingId === client.id ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />}
                      </Button>
                      {result && (
                        <Button variant="ghost" size="icon" className="size-7" title="Prepare MCA fill (Claude fills via browser extension)" onClick={() => onFileClient(client)}>
                          <MonitorPlay className="size-4" />
                        </Button>
                      )}
                      <Button variant="ghost" size="icon" className="size-7" title="View details" onClick={() => onOpenClient(client.id)}>
                        <ArrowUpRight className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-7" title="Edit client" onClick={() => onEditClient(client)}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-7 text-red-600 hover:text-red-700" title="Remove client" onClick={() => onRemoveClient(client)}>
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
            {visible.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground text-sm">
                  No clients match this filter.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
