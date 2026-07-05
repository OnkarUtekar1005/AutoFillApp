import { useEffect, useState } from 'react'
import { Sparkles, Sparkle, CircleSlash, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

// Shows whether the backend is using Claude to clean/structure extracted data.
// Polls /api/claude-status so it reflects the server's live env (it changes only
// when the server is restarted with different AOC4_* flags). This is the visible
// signal that was missing when an extraction silently fell back to raw regex.
const META = {
  full: {
    label: 'Claude: clean structuring',
    title: 'AOC4_ALLOW_CLAUDE=1 + AOC4_CLAUDE_FULL=1 — Claude re-extracts and cleans every field (best data).',
    className: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-500/10 dark:text-green-400 dark:border-green-500/20',
    Icon: Sparkles,
  },
  gapfill: {
    label: 'Claude: gap-fill only',
    title: 'AOC4_ALLOW_CLAUDE=1 — Claude fills only missing/low fields; regex output is kept (values may be dirty).',
    className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20',
    Icon: Sparkle,
  },
  off: {
    label: 'Claude: off (raw regex)',
    title: 'Claude cleaning is OFF — extraction uses raw regex, so values are dirty. Restart the server with AOC4_ALLOW_CLAUDE=1 and AOC4_CLAUDE_FULL=1.',
    className: 'bg-muted text-muted-foreground border-border',
    Icon: CircleSlash,
  },
}

export default function ClaudeStatusBadge() {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch('/api/claude-status')
        const data = await res.json()
        if (!cancelled) setStatus(data)
      } catch { /* server not up — leave as loading */ }
    }
    load()
    const id = setInterval(load, 20000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  if (!status) {
    return (
      <Badge variant="outline" className="gap-1.5 text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin" /> Claude: checking…
      </Badge>
    )
  }

  const meta = META[status.mode] || META.off
  const { Icon } = meta
  const title = status.cli_found ? meta.title : 'The `claude` CLI was not found on PATH — install it and log in to your Claude Max/Pro subscription.'
  return (
    <Badge variant="outline" className={cn('gap-1.5', meta.className)} title={title}>
      <Icon className="size-3.5" /> {meta.label}
    </Badge>
  )
}
