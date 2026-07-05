import { ClipboardList, AlertTriangle, CheckCircle2, Target, Scale, FileX2, FileCheck2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Card, CardContent } from '@/components/ui/card'

const TONE = {
  emerald: 'text-emerald-600 dark:text-emerald-400',
  amber: 'text-amber-600 dark:text-amber-400',
  red: 'text-red-600 dark:text-red-400',
  muted: 'text-muted-foreground',
}

export default function SummaryCards({ filing }) {
  const v = filing.validation || {}
  const fields = filing.fields || {}

  const total = filing.total_fields_extracted || 0
  const missing = v.missing_mandatory?.length ?? 0
  const lowConf = v.low_confidence?.length ?? 0
  const highConf = Object.values(fields).filter(f => f.confidence === 'HIGH').length
  const docErrors = filing.documents?.filter(d => d.status === 'error').length ?? 0

  const cards = [
    {
      label: 'Fields Extracted',
      value: total,
      sub: 'of 72 AOC-4 fields',
      tone: total > 50 ? 'emerald' : total > 30 ? 'amber' : 'red',
      icon: ClipboardList,
    },
    {
      label: 'Mandatory Missing',
      value: missing,
      sub: missing === 0 ? 'All mandatory found' : 'Need manual entry',
      tone: missing === 0 ? 'emerald' : missing < 5 ? 'amber' : 'red',
      icon: missing === 0 ? CheckCircle2 : AlertTriangle,
    },
    {
      label: 'High Confidence',
      value: highConf,
      sub: `${lowConf} low confidence`,
      tone: lowConf === 0 ? 'emerald' : 'amber',
      icon: Target,
    },
    {
      label: 'Balance Sheet',
      value: v.balance_check === 'PASS' ? 'PASS' : v.balance_check ? 'FAIL' : 'N/A',
      sub: v.balance_check === 'PASS' ? 'Assets = Liabilities + Equity' : v.balance_check || 'Insufficient data',
      tone: v.balance_check === 'PASS' ? 'emerald' : v.balance_check ? 'red' : 'muted',
      icon: Scale,
    },
    {
      label: 'File Errors',
      value: docErrors,
      sub: docErrors === 0 ? 'All files processed' : `${docErrors} file(s) failed`,
      tone: docErrors === 0 ? 'emerald' : 'red',
      icon: docErrors === 0 ? FileCheck2 : FileX2,
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 px-6 py-4 border-b bg-muted/30">
      {cards.map((card, i) => (
        <Card key={i} size="sm" className="shadow-none">
          <CardContent className="px-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground font-medium">{card.label}</span>
              <card.icon className={cn('size-3.5', TONE[card.tone])} />
            </div>
            <p className={cn('text-2xl font-heading font-semibold', TONE[card.tone])}>{card.value}</p>
            <p className="text-xs mt-0.5 text-muted-foreground truncate">{card.sub}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
