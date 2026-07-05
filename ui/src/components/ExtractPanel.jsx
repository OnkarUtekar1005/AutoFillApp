import { useState } from 'react'
import { Zap, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'

export default function ExtractPanel({ onExtract, loading }) {
  const [path, setPath] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (path.trim()) onExtract(path.trim())
  }

  return (
    <Card>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex gap-3">
          <Input
            type="text"
            value={path}
            onChange={e => setPath(e.target.value)}
            placeholder="e.g. D:\Data"
            className="font-mono"
            disabled={loading}
          />
          <Button type="submit" disabled={loading || !path.trim()} className="shrink-0">
            {loading ? (
              <>
                <Loader2 className="animate-spin" />
                Extracting...
              </>
            ) : (
              <>
                <Zap />
                Extract
              </>
            )}
          </Button>
        </form>
        <p className="text-xs text-muted-foreground mt-3">
          Paste the root folder containing your client sub-folders (each named{' '}
          <code className="font-mono text-foreground/80">ClientName_CIN</code>, with{' '}
          <code className="font-mono text-foreground/80">data\</code> and{' '}
          <code className="font-mono text-foreground/80">attachments\</code>)
        </p>
      </CardContent>
    </Card>
  )
}
