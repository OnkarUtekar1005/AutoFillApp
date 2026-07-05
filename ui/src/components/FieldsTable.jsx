import { useState } from 'react'
import { Search, ChevronDown, ChevronRight, ClipboardX } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { EmptyState } from './DocumentsTable'

// Mirrors extractor/mapping/schema.py SECTIONS (order matters).
const SECTION_LABELS = {
  company_identity: 'Part A — Company Identity',
  signatories: 'Part A — Signatories',
  agm: 'Part A — AGM Details',
  subsidiary: 'Part A — Subsidiary / Holding',
  auditor: 'Part A — Auditor Details',
  general_other: 'Part A — General & Other Info',
  bs_equity_liabilities: 'Part B — Balance Sheet: Equity & Liabilities',
  bs_assets: 'Part B — Balance Sheet: Assets',
  bs_breakup: 'Balance Sheet — Break-up',
  financial_parameters: 'III — Financial Parameters (BS)',
  share_capital_raised: 'IV — Share Capital Raised',
  sbn_cost: 'V & VI — SBN & Cost Records',
  pnl_revenue: 'P&L — Revenue',
  pnl_expenses: 'P&L — Expenses',
  pnl_profit: 'P&L — Profit & Tax',
  forex_params: 'P&L — Forex & Parameters',
  products_services: 'IV — Principal Products/Services',
  related_party: 'Segment III — Related Party',
  cag_report: "Segment IV — Auditor's Report / CAG",
  csr: 'Segment V — CSR',
  misc_secretarial: 'Segment VI — Misc / Secretarial Audit',
  attachments_meta: 'Attachments',
  declaration: 'Declaration',
  certificate: 'Certificate by Professional',
  office_use: 'For Office Use (MCA)',
  prior_year: 'Prior Year Comparatives',
}

const SECTION_ORDER = Object.keys(SECTION_LABELS)

const CONF_CLASSES = {
  HIGH: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/25',
  MED: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/25',
  LOW: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/25',
  LLM: 'bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-500/10 dark:text-violet-400 dark:border-violet-500/25',
}

export default function FieldsTable({ filing }) {
  const fields = filing.fields || {}
  const missingMandatory = new Set(filing.validation?.missing_mandatory || [])
  const [searchTerm, setSearchTerm] = useState('')
  const [showMissingOnly, setShowMissingOnly] = useState(false)

  const grouped = {}
  for (const [key, fieldData] of Object.entries(fields)) {
    const sec = fieldData.section || 'company_info'
    if (!grouped[sec]) grouped[sec] = []
    grouped[sec].push({ key, ...fieldData })
  }

  for (const key of missingMandatory) {
    if (!fields[key]) {
      const sec = guessSection(key)
      if (!grouped[sec]) grouped[sec] = []
      grouped[sec].push({ key, value: null, confidence: null, missing: true })
    }
  }

  const sections = SECTION_ORDER.filter(s => grouped[s]?.length > 0)

  const filterRows = (rows) => {
    let filtered = rows
    if (showMissingOnly) filtered = filtered.filter(r => r.missing || missingMandatory.has(r.key))
    if (searchTerm) {
      const t = searchTerm.toLowerCase()
      filtered = filtered.filter(r =>
        r.key.toLowerCase().includes(t) ||
        String(r.value ?? '').toLowerCase().includes(t) ||
        (r.label ?? '').toLowerCase().includes(t)
      )
    }
    return filtered
  }

  const totalExtracted = Object.keys(fields).length
  const hasMissing = missingMandatory.size > 0

  return (
    <div>
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search field name or value..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="pl-8"
          />
        </div>
        {hasMissing && (
          <Button
            variant={showMissingOnly ? 'destructive' : 'outline'}
            onClick={() => setShowMissingOnly(!showMissingOnly)}
          >
            {showMissingOnly ? 'Showing missing only' : `Show missing (${missingMandatory.size})`}
          </Button>
        )}
      </div>

      <div className="space-y-3">
        {sections.map(sec => {
          const rows = filterRows(grouped[sec] || [])
          if (rows.length === 0) return null
          return (
            <SectionBlock
              key={sec}
              title={SECTION_LABELS[sec] || sec}
              rows={rows}
              missingMandatory={missingMandatory}
            />
          )
        })}
        {totalExtracted === 0 && !hasMissing && (
          <EmptyState message="No fields extracted from this filing" />
        )}
      </div>
    </div>
  )
}

function SectionBlock({ title, rows, missingMandatory }) {
  const [collapsed, setCollapsed] = useState(false)
  const missingCount = rows.filter(r => r.missing || missingMandatory.has(r.key)).length

  return (
    <div className="rounded-lg border overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-muted/40 hover:bg-muted transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          {collapsed ? <ChevronRight className="size-4 text-muted-foreground" /> : <ChevronDown className="size-4 text-muted-foreground" />}
          <span className="font-medium text-sm">{title}</span>
          <span className="text-xs text-muted-foreground">{rows.length} field{rows.length !== 1 ? 's' : ''}</span>
          {missingCount > 0 && (
            <Badge variant="destructive" className="text-[10px] h-4">{missingCount} missing</Badge>
          )}
        </div>
      </button>

      {!collapsed && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-48">Field</TableHead>
              <TableHead>Value</TableHead>
              <TableHead className="w-24">Confidence</TableHead>
              <TableHead className="w-36">Source File</TableHead>
              <TableHead className="w-16">Page</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(row => (
              <FieldRow key={row.key} row={row} isMissing={row.missing || missingMandatory.has(row.key)} />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

function FieldRow({ row, isMissing }) {
  const conf = row.confidence
  const sourceFile = row.source_file?.split(/[\\/]/).pop() || row.source_file || '—'

  return (
    <TableRow className={isMissing ? 'bg-red-50/60 dark:bg-red-500/5' : ''}>
      <TableCell>
        <span className={cn('font-mono text-xs', isMissing && 'text-red-700 dark:text-red-400')}>{row.key}</span>
        {isMissing && (
          <Badge variant="destructive" className="ml-1.5 text-[10px] h-4 uppercase">missing</Badge>
        )}
      </TableCell>
      <TableCell className="whitespace-normal break-all">
        {isMissing ? (
          <span className="text-muted-foreground/70 italic text-xs flex items-center gap-1">
            <ClipboardX className="size-3.5" /> not extracted
          </span>
        ) : (
          <span className="font-medium">{formatValue(row.value)}</span>
        )}
      </TableCell>
      <TableCell>
        {conf ? (
          <Badge variant="outline" className={cn('gap-1', CONF_CLASSES[conf])}>
            <span className="size-1.5 rounded-full bg-current" />
            {conf}
          </Badge>
        ) : '—'}
      </TableCell>
      <TableCell>
        <span className="text-xs text-muted-foreground font-mono truncate block max-w-xs" title={row.source_file}>{sourceFile}</span>
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {row.page != null ? row.page : '—'}
      </TableCell>
    </TableRow>
  )
}

function formatValue(val) {
  if (val == null) return '—'
  if (typeof val === 'number') return val.toLocaleString('en-IN')
  return String(val)
}

function guessSection(key) {
  if (key.endsWith('_prior_year')) return 'prior_year'
  if (key.includes('total_assets') || key.includes('property_plant') || key.includes('intangible') || key.includes('wip') || key.includes('inventor') || key.includes('receivable') || key.includes('cash') || key.includes('current_assets')) return 'bs_assets'
  if (key.includes('total_liabilities_equity') || key.includes('share_capital') || key.includes('reserves') || key.includes('borrowing') || key.includes('payable') || key.includes('provision') || key.includes('warrant')) return 'bs_equity_liabilities'
  if (key.startsWith('revenue') || key.includes('income') || key.includes('turnover')) return 'pnl_revenue'
  if (key.includes('expense') || key.includes('depreciation') || key.includes('cost') || key.includes('finance_cost') || key.includes('remuneration')) return 'pnl_expenses'
  if (key.includes('profit') || key.includes('tax') || key.includes('eps')) return 'pnl_profit'
  if (key.startsWith('auditor')) return 'auditor'
  if (key.startsWith('fs_sig') || key.startsWith('br_sig') || key.includes('board_report_date')) return 'signatories'
  if (key.startsWith('agm')) return 'agm'
  return 'company_identity'
}
