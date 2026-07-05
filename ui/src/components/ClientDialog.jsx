import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/**
 * Add or edit a single client (name, CIN, data-folder path).
 * `client` = null → add mode; an object → edit mode.
 */
export default function ClientDialog({ open, onOpenChange, client, onSave }) {
  const editing = Boolean(client)
  const [name, setName] = useState('')
  const [cin, setCin] = useState('')
  const [path, setPath] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (open) {
      setName(client?.name || '')
      setCin(client?.cin || '')
      setPath(client?.path || '')
      setError(null)
    }
  }, [open, client])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSave({ id: client?.id, name: name.trim(), cin: cin.trim(), path: path.trim() })
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
            <DialogTitle>{editing ? 'Edit client' : 'Add client'}</DialogTitle>
            <DialogDescription>
              Each client has its own name, CIN, and data-folder path.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-1.5">
              <Label htmlFor="c-name">Client name</Label>
              <Input id="c-name" value={name} onChange={e => setName(e.target.value)} placeholder="Acme Steel Pvt Ltd" autoFocus />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="c-cin">CIN <span className="text-muted-foreground font-normal">(optional)</span></Label>
              <Input id="c-cin" value={cin} onChange={e => setCin(e.target.value)} placeholder="U27100MH2019PTC111111" className="font-mono" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="c-path">Data folder path</Label>
              <Input id="c-path" value={path} onChange={e => setPath(e.target.value)} placeholder="D:\Clients\Acme_U27100MH2019PTC111111" className="font-mono" />
              <p className="text-xs text-muted-foreground">
                Folder with the source documents, or a <code className="font-mono">ClientName_CIN</code> folder containing <code className="font-mono">data\</code> + <code className="font-mono">attachments\</code>.
              </p>
            </div>
            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}
              {editing ? 'Save changes' : 'Add client'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
