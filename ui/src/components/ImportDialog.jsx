import { useState, useEffect } from 'react'
import { Loader2, FolderSearch } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/** Bulk-add clients by scanning a root folder of ClientName_CIN sub-folders. */
export default function ImportDialog({ open, onOpenChange, onImport }) {
  const [folder, setFolder] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { if (open) { setFolder(''); setError(null) } }, [open])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onImport(folder.trim())
      onOpenChange(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Import clients from a folder</DialogTitle>
            <DialogDescription>
              Scans a root folder and adds every <code className="font-mono">ClientName_CIN</code> sub-folder as a client.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5 py-4">
            <Label htmlFor="imp-folder">Root folder</Label>
            <Input id="imp-folder" value={folder} onChange={e => setFolder(e.target.value)} placeholder="D:\Data" className="font-mono" autoFocus />
            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={busy || !folder.trim()}>
              {busy ? <Loader2 className="animate-spin" /> : <FolderSearch />}
              Import
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
