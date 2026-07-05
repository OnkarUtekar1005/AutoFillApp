import { useEffect, useState, useCallback } from 'react'
import { X, Trash2, RefreshCw, ListChecks } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardAction, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { getFillQueue, removeFillJob, clearFillQueue } from '@/lib/api'

// View + management of the auto-fill queue. A running filler session pulls jobs
// from here; this panel lets you cancel a pending job, kill a stuck one, or clear
// finished/all rows. Loads once on open, then updates ONLY when you click Refresh
// (no auto-polling).
const STATUS = {
  pending: { label: 'Queued', className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400' },
  in_progress: { label: 'Filling', className: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400' },
  done: { label: 'Filled', className: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-500/10 dark:text-green-400' },
  error: { label: 'Error', className: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-400' },
}

export default function QueuePanel() {
  const [jobs, setJobs] = useState([])
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try { setJobs(await getFillQueue()) } catch { /* backend momentarily down */ }
  }, [])

  // Load once when the panel opens; after that only the Refresh button re-pulls.
  useEffect(() => { load() }, [load])

  async function remove(jobId) {
    setBusy(true)
    try { setJobs(await removeFillJob(jobId)) } catch { /* ignore */ } finally { setBusy(false) }
  }
  async function clear(scope) {
    setBusy(true)
    try { setJobs(await clearFillQueue(scope)) } catch { /* ignore */ } finally { setBusy(false) }
  }

  const active = jobs.filter(j => j.status === 'pending' || j.status === 'in_progress').length

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="text-base flex items-center gap-2">
          <ListChecks className="size-4" /> Auto-fill queue
          {active > 0 && <Badge variant="outline" className="ml-1">{active} active</Badge>}
        </CardTitle>
        <CardAction className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={load} title="Refresh"><RefreshCw className="size-4" /></Button>
          <Button variant="outline" size="sm" onClick={() => clear('finished')} disabled={busy}>Clear finished</Button>
          <Button variant="outline" size="sm" onClick={() => clear('all')} disabled={busy}>
            <Trash2 className="size-4" /> Clear all
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="p-0">
        {jobs.length === 0 ? (
          <p className="px-6 py-6 text-sm text-muted-foreground text-center">
            Queue is empty. Click <b>Auto-fill (agent)</b> on a client to queue a fill.
          </p>
        ) : (
          <ul className="divide-y">
            {jobs.map(job => {
              const s = STATUS[job.status] || STATUS.pending
              return (
                <li key={job.id} className="flex items-center gap-3 px-6 py-2.5 text-sm">
                  <span className="font-mono text-xs text-muted-foreground w-8">#{job.id}</span>
                  <Badge variant="outline" className={cn('gap-1.5 shrink-0', s.className)}>{s.label}</Badge>
                  <span className="font-medium truncate">{job.client_name}</span>
                  {job.worker && <span className="text-xs text-muted-foreground">worker {job.worker}</span>}
                  {job.message && <span className="text-xs text-muted-foreground truncate">— {job.message}</span>}
                  <Button
                    variant="ghost" size="sm" className="ml-auto shrink-0 text-muted-foreground hover:text-red-600"
                    onClick={() => remove(job.id)} disabled={busy}
                    title={job.status === 'pending' ? 'Cancel this queued job' : 'Remove from queue'}
                  >
                    <X className="size-4" />
                  </Button>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
