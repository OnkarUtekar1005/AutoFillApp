import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  FileSpreadsheet, AlertTriangle, ArrowLeft, LayoutDashboard,
  Plus, FolderSearch, Zap, Loader2, Users, FlaskConical,
} from 'lucide-react'

const API_ORIGIN = 'http://localhost:8000'
import DashboardOverview from './components/DashboardOverview'
import ClientDialog from './components/ClientDialog'
import ImportDialog from './components/ImportDialog'
import ClientList from './components/ClientList'
import ResultsView from './components/ResultsView'
import ClaudeStatusBadge from './components/ClaudeStatusBadge'
import QueuePanel from './components/QueuePanel'
import { getFillData, enqueueFill } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import './index.css'

const jsonHeaders = { 'Content-Type': 'application/json' }

export default function App() {
  const [clients, setClients] = useState([])
  const [results, setResults] = useState([]) // extracted filings
  const [view, setView] = useState('overview')
  const [selectedClientId, setSelectedClientId] = useState(null)
  const [booting, setBooting] = useState(true)
  const [extracting, setExtracting] = useState(false)
  const [extractingId, setExtractingId] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const [clientDialog, setClientDialog] = useState({ open: false, client: null })
  const [importOpen, setImportOpen] = useState(false)
  const [schemaFields, setSchemaFields] = useState([])
  const [sections, setSections] = useState({})

  // Land on the dashboard: load registered clients + their cached results.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch('/api/state')
        const data = await res.json()
        if (cancelled) return
        setClients(data.clients || [])
        setResults(data.filings || [])
      } catch { /* server not up yet */ }
      finally { if (!cancelled) setBooting(false) }
    })()
    return () => { cancelled = true }
  }, [])

  // Field schema (for the editable Manual Entry tab + section labels).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch('/api/schema')
        const data = await res.json()
        if (cancelled) return
        setSchemaFields(data.fields || [])
        setSections(data.sections || {})
      } catch { /* ignore */ }
    })()
    return () => { cancelled = true }
  }, [])

  const manualFields = useMemo(() => schemaFields.filter(f => f.source === 'MANUAL'), [schemaFields])
  const [progress, setProgress] = useState(null)

  // Poll a background extraction job until done/error; returns its filings.
  async function pollJob(jobKey, onProgress) {
    const sleep = ms => new Promise(r => setTimeout(r, ms))
    // eslint-disable-next-line no-constant-condition
    while (true) {
      await sleep(2000)
      const res = await fetch(`/api/jobs/${encodeURIComponent(jobKey)}`)
      const data = await res.json()
      if (data.progress && onProgress) onProgress(data.progress)
      if (data.status === 'done') return data.filings || []
      if (data.status === 'error') throw new Error(data.error || 'Extraction failed')
      if (data.status === 'unknown') throw new Error('Job not found (server may have restarted)')
    }
  }

  async function saveManual(clientId, values) {
    const res = await fetch('/api/manual', {
      method: 'POST', headers: jsonHeaders,
      body: JSON.stringify({ client_id: clientId, values }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Could not save manual fields')
    // Replace the updated client's result(s) in state.
    const updated = data.filings || []
    if (updated.length) {
      setResults(prev => {
        const client = clients.find(c => c.id === clientId)
        const others = prev.filter(r => !client || !((client.cin && r.cin === client.cin) || r.client_name === client.name))
        return [...others, ...updated]
      })
    }
  }

  const refreshClients = useCallback(async () => {
    const res = await fetch('/api/clients')
    const data = await res.json()
    setClients(data.clients || [])
  }, [])

  function resultForClient(client) {
    return results.find(r =>
      (client.cin && r.cin && r.cin === client.cin) || r.client_name === client.name
    ) || null
  }
  const rows = clients.map(client => ({ client, result: resultForClient(client) }))

  async function saveClient({ id, name, cin, path }) {
    const url = id ? `/api/clients/${id}` : '/api/clients'
    const res = await fetch(url, { method: id ? 'PUT' : 'POST', headers: jsonHeaders, body: JSON.stringify({ name, cin, path }) })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Could not save client')
    await refreshClients()
  }

  async function removeClient(client) {
    if (!window.confirm(`Remove "${client.name}" from the client list?\n(This only removes it from the dashboard — your files are not deleted.)`)) return
    const res = await fetch(`/api/clients/${client.id}`, { method: 'DELETE' })
    if (res.ok) {
      setResults(prev => prev.filter(r => !((client.cin && r.cin === client.cin) || r.client_name === client.name)))
      await refreshClients()
    }
  }

  async function importClients(folder) {
    const res = await fetch('/api/clients/import', { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ folder }) })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Import failed')
    setClients(data.clients || [])
    setNotice({ ok: true, message: `Imported ${data.added} client${data.added !== 1 ? 's' : ''}. Click "Extract All" to process them.` })
  }

  async function extractAll() {
    if (clients.length === 0) { setNotice({ ok: false, message: 'Add or import clients first.' }); return }
    setExtracting(true)
    setError(null)
    setNotice(null)
    setProgress(null)
    try {
      const res = await fetch('/api/extract', { method: 'POST', headers: jsonHeaders })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Extraction failed')
      const filings = await pollJob(data.job, setProgress)
      setResults(filings)
      setNotice({ ok: true, message: `Extracted ${filings.length} filing${filings.length !== 1 ? 's' : ''}.` })
    } catch (e) {
      setError(e.message)
    } finally {
      setExtracting(false)
      setProgress(null)
    }
  }

  async function extractClient(client) {
    setExtractingId(client.id)
    setError(null)
    setNotice(null)
    try {
      const res = await fetch(`/api/clients/${client.id}/extract`, { method: 'POST', headers: jsonHeaders })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Extraction failed')
      const updated = await pollJob(data.job)
      setResults(prev => {
        const others = prev.filter(r => !((client.cin && r.cin === client.cin) || r.client_name === client.name))
        return [...others, ...updated]
      })
      const one = updated[0]
      if (one?.excel_path) setNotice({ ok: true, message: `Extracted ${client.name}. Excel saved to: ${one.excel_path}` })
      else setNotice({ ok: false, message: `${client.name}: ${one?.documents?.[0]?.error || 'no data extracted — check the folder path and files.'}` })
    } catch (e) {
      setError(e.message)
    } finally {
      setExtractingId(null)
    }
  }

  async function fileClient(client) {
    try {
      const data = await getFillData(client.id)
      const count = data.filings?.[0]?.fields?.length || 0
      if (count === 0) {
        setNotice({ ok: false, message: `${client.name}: no extracted data yet — run Extract first.` })
        return
      }
      setNotice({
        ok: true,
        message: `${client.name}: ${count} fields ready to fill on MCA. Open the AOC-4 form in Chrome (already logged in), then ask Claude: "fill ${client.name} on the MCA form". Claude fills each field via the browser extension and stops before DSC signing and submit.`,
      })
    } catch (e) {
      setNotice({ ok: false, message: e.message })
    }
  }

  async function queueFill(client) {
    try {
      const data = await getFillData(client.id)
      const count = data.filings?.[0]?.fields?.length || 0
      if (count === 0) {
        setNotice({ ok: false, message: `${client.name}: no extracted data yet — run Extract first.` })
        return
      }
      const job = await enqueueFill(client.id)
      setNotice({
        ok: true,
        message: `${client.name}: queued to auto-fill (job #${job.id}, ${count} fields). A running Claude Code filler session will pick it up and fill the open form — no paste.`,
      })
    } catch (e) {
      setNotice({ ok: false, message: e.message })
    }
  }

  function handleRevalidated(clientId, revalidateResult) {
    const client = clients.find(c => c.id === clientId)
    if (!client) return
    const status = revalidateResult.status === 'Fields OK' ? 'Ready' : revalidateResult.status
    setResults(prev => prev.map(r =>
      ((client.cin && r.cin === client.cin) || r.client_name === client.name)
        ? { ...r, validation: revalidateResult.validation, status }
        : r
    ))
  }

  function openClient(clientId) {
    setSelectedClientId(clientId)
    setView('detail')
  }

  const extractedResults = results
  const selectedClient = clients.find(c => c.id === selectedClientId)
  const selectedResult = selectedClient ? resultForClient(selectedClient) : null
  const selectedIndex = selectedResult ? extractedResults.indexOf(selectedResult) : 0
  const hasClients = clients.length > 0

  return (
    <div className="min-h-screen bg-muted/20">
      <header className="bg-card border-b px-6 py-3 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <FileSpreadsheet className="size-5" />
            </div>
            <div>
              <h1 className="font-heading text-base font-semibold leading-tight">AOC-4 Filing Dashboard</h1>
              <p className="text-xs text-muted-foreground">
                {hasClients ? `${clients.length} client${clients.length !== 1 ? 's' : ''} managed` : 'Extraction & readiness across all clients'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <ClaudeStatusBadge />
            <Button variant="outline" size="sm" onClick={() => window.open(`${API_ORIGIN}/test-form`, '_blank')} title="Open the mock AOC-4 form to test filling via the Claude browser extension">
              <FlaskConical /> Test form
            </Button>
            <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}>
              <FolderSearch /> Import folder
            </Button>
            <Button variant="outline" size="sm" onClick={() => setClientDialog({ open: true, client: null })}>
              <Plus /> Add client
            </Button>
            <Button size="sm" onClick={extractAll} disabled={extracting || !hasClients}>
              {extracting ? <Loader2 className="animate-spin" /> : <Zap />}
              {extracting ? 'Extracting...' : 'Extract All'}
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-5">
        {booting && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        )}

        {notice && (
          <Card className={notice.ok
            ? 'border-emerald-200 bg-emerald-50/60 dark:border-emerald-500/25 dark:bg-emerald-500/5'
            : 'border-amber-200 bg-amber-50/60 dark:border-amber-500/25 dark:bg-amber-500/5'}>
            <CardContent className="flex items-start justify-between gap-3 text-sm">
              <span className={notice.ok ? 'text-emerald-800 dark:text-emerald-400' : 'text-amber-800 dark:text-amber-400'}>{notice.message}</span>
              <button className="text-muted-foreground hover:text-foreground text-xs" onClick={() => setNotice(null)}>Dismiss</button>
            </CardContent>
          </Card>
        )}

        {error && (
          <Card className="border-red-200 bg-red-50/60 dark:border-red-500/25 dark:bg-red-500/5">
            <CardContent className="flex gap-3 items-start">
              <AlertTriangle className="size-5 text-red-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-red-800 dark:text-red-400">Extraction failed</p>
                <p className="text-sm text-red-600 dark:text-red-400/80 mt-1 font-mono">{error}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {extracting && (
          <Card>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-3">
                <Loader2 className="size-5 animate-spin text-primary" />
                <div className="flex-1">
                  <p className="text-sm font-medium">
                    {progress
                      ? `Extracting ${progress.current || '…'} (${progress.done}/${progress.total})`
                      : 'Starting extraction…'}
                  </p>
                  <p className="text-xs text-muted-foreground">Large scanned PDFs + AI cleaning can take a few minutes per client.</p>
                </div>
              </div>
              {progress?.total > 0 && (
                <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                  <div className="h-full bg-primary transition-all" style={{ width: `${Math.round((progress.done / progress.total) * 100)}%` }} />
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {!booting && !hasClients && !extracting && <EmptySetup onAdd={() => setClientDialog({ open: true, client: null })} onImport={() => setImportOpen(true)} />}

        {!booting && hasClients && view === 'overview' && !extracting && (
          <div className="space-y-4">
            <DashboardOverview
              rows={rows}
              extractingId={extractingId}
              onOpenClient={openClient}
              onExtractClient={extractClient}
              onEditClient={(client) => setClientDialog({ open: true, client })}
              onRemoveClient={removeClient}
              onFileClient={fileClient}
              onQueueFill={queueFill}
            />
            <QueuePanel />
          </div>
        )}

        {hasClients && view === 'detail' && selectedClient && (
          <div className="space-y-4">
            <Button variant="ghost" size="sm" onClick={() => setView('overview')} className="-ml-2">
              <ArrowLeft /><LayoutDashboard className="size-4" /> Back to dashboard
            </Button>
            {selectedResult ? (
              <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5 items-start">
                <ClientList filings={extractedResults} selected={selectedIndex} onSelect={(i) => {
                  const r = extractedResults[i]
                  const c = clients.find(cl => (cl.cin && r.cin === cl.cin) || cl.name === r.client_name)
                  if (c) setSelectedClientId(c.id)
                }} />
                <ResultsView
                  filing={selectedResult}
                  clientId={selectedClientId}
                  manualFields={manualFields}
                  sections={sections}
                  extracting={extractingId === selectedClientId}
                  onExtract={() => extractClient(selectedClient)}
                  onRevalidated={(r) => handleRevalidated(selectedClientId, r)}
                  onSaveManual={(values) => saveManual(selectedClientId, values)}
                  onFile={() => fileClient(selectedClient)}
                  onQueueFill={() => queueFill(selectedClient)}
                />
              </div>
            ) : (
              <Card>
                <CardContent className="py-10 flex flex-col items-center text-center gap-4">
                  <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Zap className="size-6" />
                  </div>
                  <div>
                    <h2 className="font-heading text-lg font-semibold">{selectedClient.name}</h2>
                    <p className="text-sm text-muted-foreground font-mono">{selectedClient.cin || 'CIN not found'}</p>
                    <p className="text-sm text-muted-foreground mt-1">Not extracted yet — run extraction to pull fields and write the Excel.</p>
                  </div>
                  <Button onClick={() => extractClient(selectedClient)} disabled={extractingId === selectedClient.id}>
                    {extractingId === selectedClient.id ? <Loader2 className="animate-spin" /> : <Zap />}
                    {extractingId === selectedClient.id ? 'Extracting...' : 'Extract this client'}
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </main>

      <ClientDialog
        open={clientDialog.open}
        client={clientDialog.client}
        onOpenChange={(open) => setClientDialog(s => ({ ...s, open }))}
        onSave={saveClient}
      />
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} onImport={importClients} />
    </div>
  )
}

function EmptySetup({ onAdd, onImport }) {
  return (
    <Card>
      <CardContent className="py-10 flex flex-col items-center text-center gap-4 max-w-xl mx-auto">
        <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Users className="size-6" />
        </div>
        <div>
          <h2 className="font-heading text-lg font-semibold">No clients yet</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Add a client with its own name, CIN and data-folder path — or import a whole folder of{' '}
            <code className="font-mono">ClientName_CIN</code> sub-folders at once.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onImport}><FolderSearch /> Import folder</Button>
          <Button onClick={onAdd}><Plus /> Add client</Button>
        </div>
      </CardContent>
    </Card>
  )
}
