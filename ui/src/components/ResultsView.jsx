import { useState } from 'react'
import { Download, RefreshCw, Loader2, CheckCircle2, XCircle, MinusCircle, MonitorPlay, Zap, FlaskConical } from 'lucide-react'
import { cn } from '@/lib/utils'
import { statusMeta } from '@/lib/status'
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import SummaryCards from './SummaryCards'
import DocumentsTable from './DocumentsTable'
import FieldsTable from './FieldsTable'
import AttachmentsTable from './AttachmentsTable'
import ManualEntryForm from './ManualEntryForm'

export default function ResultsView({ filing, clientId, manualFields = [], sections = {}, extracting = false, onExtract, onRevalidated, onSaveManual, onFile, onQueueFill }) {
  const [revalidating, setRevalidating] = useState(false)
  const [revalidateError, setRevalidateError] = useState(null)
  const [filingBusy, setFilingBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const s = statusMeta(filing.status)
  const StatusIcon = s.icon

  async function handleRevalidate() {
    if (!filing.excel_path) return
    setRevalidating(true)
    setRevalidateError(null)
    try {
      const res = await fetch('/api/revalidate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ excel_path: filing.excel_path }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Re-validate failed')
      onRevalidated?.(data)
    } catch (e) {
      setRevalidateError(e.message)
    } finally {
      setRevalidating(false)
    }
  }

  async function handleFile() {
    if (!onFile) return
    setFilingBusy(true)
    try {
      await onFile()
    } finally {
      setFilingBusy(false)
    }
  }

  // A web page button can't command the browser extension (security sandbox), so
  // the closest one-click hand-off is: open the form + copy a ready prompt to
  // paste into the Claude side-panel, which then fills via the extension.
  async function handleTest() {
    const url = `http://localhost:8000/test-form?client=${encodeURIComponent(clientId)}`
    window.open(url, '_blank', 'noopener,noreferrer')
    const prompt =
      `Fill "${filing.client_name}" on the open AOC-4 form using the Claude browser extension: ` +
      `read http://localhost:8000/api/clients/${clientId}/fill-data, find each field by its label, ` +
      `type the value, verify, and stop before DSC signing and submit.`
    try {
      await navigator.clipboard.writeText(prompt)
      setCopied(true)
      setTimeout(() => setCopied(false), 4000)
    } catch {
      /* clipboard blocked (non-secure context) — the tab still opens */
    }
  }

  return (
    <Card className="py-0 overflow-hidden gap-0">
      <CardHeader className="border-b py-4 px-6">
        <CardTitle className="text-base">{filing.client_name}</CardTitle>
        <CardDescription className="font-mono">{filing.cin || 'CIN not found'}</CardDescription>
        <CardDescription>
          Period: {filing.period} &nbsp;·&nbsp; {filing.total_fields_extracted} fields extracted
        </CardDescription>
        <CardAction>
          <Badge variant="outline" className={cn('gap-1.5', s.badge)}>
            <StatusIcon className="size-3.5" />
            {filing.status || 'Unknown'}
          </Badge>
        </CardAction>
      </CardHeader>

      <div className="px-6 py-3 border-b bg-muted/30 flex items-center justify-between flex-wrap gap-3">
        <div className="text-sm text-muted-foreground">
          Fix missing/low-confidence cells directly in Excel, then re-validate here.
          {filing.excel_path && (
            <span className="block font-mono text-xs mt-0.5 truncate max-w-lg opacity-70" title={filing.excel_path}>
              {filing.excel_path}
            </span>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          {onExtract && (
            <Button variant="outline" size="sm" onClick={onExtract} disabled={extracting} title="Re-extract this client (writes its Excel)">
              {extracting ? <Loader2 className="animate-spin" /> : <Zap />}
              {extracting ? 'Extracting...' : 'Extract'}
            </Button>
          )}
          {filing.excel_path && (
            <Button variant="outline" size="sm" asChild>
              <a href={`/api/download-excel?path=${encodeURIComponent(filing.excel_path)}`}>
                <Download />
                Open Excel
              </a>
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={handleRevalidate} disabled={revalidating || !filing.excel_path}>
            {revalidating ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            {revalidating ? 'Re-validating...' : 'Re-validate'}
          </Button>
          {clientId && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleTest}
              title="Open the test form in a new tab and copy the Claude prompt — paste it into the Claude side-panel to fill via the extension"
            >
              {copied ? <CheckCircle2 className="text-green-600" /> : <FlaskConical />}
              {copied ? 'Prompt copied — paste to Claude' : 'Test form'}
            </Button>
          )}
          {onQueueFill && (
            <Button
              size="sm"
              onClick={onQueueFill}
              title="Queue this client for a running Claude Code filler session to auto-fill the open form (no paste)"
            >
              <MonitorPlay />
              Auto-fill (agent)
            </Button>
          )}
          {onFile && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleFile}
              disabled={filingBusy}
              title="Prepare fill data — then paste the copied prompt into the Claude side-panel"
            >
              {filingBusy ? <Loader2 className="animate-spin" /> : <MonitorPlay />}
              Prepare MCA fill
            </Button>
          )}
        </div>
      </div>
      {revalidateError && (
        <p className="px-6 py-2 text-sm text-red-600 dark:text-red-400 border-b bg-red-50/60 dark:bg-red-500/5">{revalidateError}</p>
      )}

      <SummaryCards filing={filing} />

      <Tabs defaultValue="fields" className="gap-0">
        <TabsList variant="line" className="h-auto rounded-none border-b bg-transparent px-6 py-0 w-full justify-start flex-wrap">
          <TabsTrigger value="fields" className="py-3">Extracted Fields</TabsTrigger>
          <TabsTrigger value="manual" className="py-3">Manual Entry ({manualFields.length})</TabsTrigger>
          <TabsTrigger value="docs" className="py-3">Documents ({filing.documents?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="attachments" className="py-3">Attachments ({filing.attachments?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="validation" className="py-3">Validation</TabsTrigger>
        </TabsList>

        <div className="p-6">
          <TabsContent value="fields"><FieldsTable filing={filing} /></TabsContent>
          <TabsContent value="manual">
            {manualFields.length > 0
              ? <ManualEntryForm filing={filing} manualFields={manualFields} sections={sections} onSave={onSaveManual} />
              : <p className="text-sm text-muted-foreground">Loading field list…</p>}
          </TabsContent>
          <TabsContent value="docs"><DocumentsTable filing={filing} /></TabsContent>
          <TabsContent value="attachments"><AttachmentsTable filing={filing} /></TabsContent>
          <TabsContent value="validation"><ValidationPanel filing={filing} /></TabsContent>
        </div>
      </Tabs>
    </Card>
  )
}

function ValidationPanel({ filing }) {
  const v = filing.validation || {}
  return (
    <div className="space-y-4">
      <Section title="Missing Mandatory Fields" count={v.missing_mandatory?.length}>
        {v.missing_mandatory?.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {v.missing_mandatory.map(k => (
              <Badge key={k} variant="destructive" className="font-mono">{k}</Badge>
            ))}
          </div>
        ) : <PassLine text="All mandatory fields extracted" />}
      </Section>

      <Section title="Low Confidence Fields" count={v.low_confidence?.length}>
        {v.low_confidence?.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {v.low_confidence.map(k => (
              <Badge key={k} variant="outline" className="font-mono bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/25">{k}</Badge>
            ))}
          </div>
        ) : <PassLine text="No low confidence fields" />}
      </Section>

      <Section title="Sanity Checks">
        <div className="mt-2 space-y-2.5">
          <CheckRow label="Balance Sheet (Assets = Equity + Liabilities)" result={v.balance_check} />
          <CheckRow label="P&L (Revenue - Expenses ≈ PBT)" result={v.pnl_check} />
        </div>
      </Section>

      {v.type_errors?.length > 0 && (
        <Section title="Type Errors" count={v.type_errors.length}>
          <div className="mt-2 space-y-1">
            {v.type_errors.map(([k, msg], i) => (
              <p key={i} className="text-sm text-red-600 dark:text-red-400">
                <span className="font-mono font-semibold">{k}</span>: {msg}
              </p>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

function Section({ title, count, children }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          {title}
          {count != null && count > 0 && (
            <Badge variant="destructive" className="text-[10px] h-4">{count}</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function PassLine({ text }) {
  return (
    <p className="text-sm text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1.5">
      <CheckCircle2 className="size-4" /> {text}
    </p>
  )
}

function CheckRow({ label, result }) {
  if (!result) return (
    <div className="flex items-center gap-2 text-muted-foreground">
      <MinusCircle className="size-4" />
      <span className="text-sm">{label}: not enough data</span>
    </div>
  )
  const pass = result === 'PASS'
  return (
    <div className="flex items-start gap-2">
      {pass
        ? <CheckCircle2 className="size-4 text-emerald-500 mt-0.5 shrink-0" />
        : <XCircle className="size-4 text-red-500 mt-0.5 shrink-0" />}
      <div>
        <span className="text-sm">{label}</span>
        {!pass && <p className="text-xs text-red-600 dark:text-red-400 font-mono mt-0.5">{result}</p>}
      </div>
    </div>
  )
}
