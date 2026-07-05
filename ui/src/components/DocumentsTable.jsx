import { FileX2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const INGEST_LABELS = {
  PDF_STRUCTURED: { label: 'PDF (structured)', tone: 'ok' },
  PDF_STRUCTURED_FALLBACK: { label: 'PDF (fallback)', tone: 'warn' },
  PDF_OCR: { label: 'PDF (OCR)', tone: 'warn' },
  MARKITDOWN: { label: 'Markdown (markitdown)', tone: 'ok' },
  MARKER_FALLBACK: { label: 'Markdown (marker)', tone: 'warn' },
  CLAUDE_CONVERT_FALLBACK: { label: 'Markdown (Claude)', tone: 'warn' },
  EXCEL: { label: 'Excel', tone: 'ok' },
  WORD: { label: 'Word', tone: 'ok' },
  CSV: { label: 'CSV', tone: 'ok' },
  IMAGE_OCR: { label: 'Image (OCR)', tone: 'warn' },
  UNSUPPORTED: { label: 'Unsupported', tone: 'muted' },
}

const TONE_CLASSES = {
  ok: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/25',
  warn: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/25',
  muted: 'bg-muted text-muted-foreground',
}

export default function DocumentsTable({ filing }) {
  const docs = filing.documents || []

  if (docs.length === 0) {
    return <EmptyState message="No document records available" />
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>File</TableHead>
          <TableHead>Ingest Method</TableHead>
          <TableHead className="text-center">Items</TableHead>
          <TableHead className="text-center">Mapped</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {docs.map((doc, i) => {
          const ingest = INGEST_LABELS[doc.ingest_path] || { label: doc.ingest_path || '—', tone: 'muted' }
          const isError = doc.status === 'error'
          const fileName = doc.file_path?.split(/[\\/]/).pop() || doc.file_path || '—'

          return (
            <TableRow key={i} className={isError ? 'bg-red-50/60 dark:bg-red-500/5' : ''}>
              <TableCell className="max-w-xs">
                <span className="font-mono text-xs truncate block" title={doc.file_path}>{fileName}</span>
              </TableCell>
              <TableCell>
                <Badge variant="outline" className={TONE_CLASSES[ingest.tone]}>{ingest.label}</Badge>
              </TableCell>
              <TableCell className="text-center text-muted-foreground">{doc.items_extracted ?? '—'}</TableCell>
              <TableCell className="text-center text-muted-foreground">{doc.fields_mapped ?? '—'}</TableCell>
              <TableCell>
                {isError ? (
                  <div>
                    <Badge variant="destructive">ERROR</Badge>
                    {doc.error && (
                      <p className="text-xs text-red-600 dark:text-red-400 font-mono mt-1 max-w-sm truncate" title={doc.error}>
                        {doc.error}
                      </p>
                    )}
                  </div>
                ) : (
                  <Badge className={TONE_CLASSES.ok} variant="outline">OK</Badge>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}

export function EmptyState({ message }) {
  return (
    <div className="flex flex-col items-center gap-2 text-center py-10 text-muted-foreground">
      <FileX2 className="size-6" />
      <p className="text-sm">{message}</p>
    </div>
  )
}
