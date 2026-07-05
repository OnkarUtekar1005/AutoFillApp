import { useState } from 'react'
import { FolderInput, RotateCw, Loader2, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

/**
 * Compact toolbar shown once a folder is loaded: displays the current folder
 * with Re-extract, and an inline editor to switch folders. The full-screen
 * "paste a path" prompt is only for the first run (see SetupPanel).
 */
export default function FolderBar({ folder, clientCount, loading, onExtract }) {
  const [editing, setEditing] = useState(false)
  const [path, setPath] = useState(folder || '')

  function submit(e) {
    e.preventDefault()
    if (path.trim()) {
      onExtract(path.trim())
      setEditing(false)
    }
  }

  if (editing) {
    return (
      <form onSubmit={submit} className="flex items-center gap-2">
        <Input
          autoFocus
          value={path}
          onChange={e => setPath(e.target.value)}
          placeholder="e.g. D:\Data"
          className="font-mono h-9 max-w-md"
          disabled={loading}
        />
        <Button type="submit" size="sm" disabled={loading || !path.trim()}>
          {loading ? <Loader2 className="animate-spin" /> : <Check />} Extract
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => { setEditing(false); setPath(folder || '') }}>
          <X />
        </Button>
      </form>
    )
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex items-center gap-2 min-w-0">
        <FolderInput className="size-4 text-muted-foreground shrink-0" />
        <span className="font-mono text-sm truncate max-w-md" title={folder}>{folder}</span>
        {clientCount != null && (
          <span className="text-xs text-muted-foreground shrink-0">· {clientCount} client{clientCount !== 1 ? 's' : ''}</span>
        )}
      </div>
      <div className="flex items-center gap-2 ml-auto">
        <Button variant="outline" size="sm" onClick={() => onExtract(folder)} disabled={loading}>
          {loading ? <Loader2 className="animate-spin" /> : <RotateCw />}
          Re-extract
        </Button>
        <Button variant="ghost" size="sm" onClick={() => { setPath(folder || ''); setEditing(true) }} disabled={loading}>
          <FolderInput />
          Change folder
        </Button>
      </div>
    </div>
  )
}
