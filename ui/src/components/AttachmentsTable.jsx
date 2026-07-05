import { Paperclip, FileWarning, ListChecks } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardAction, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const CHECKLIST = [
  'Balance Sheet', 'Profit & Loss Statement', 'Cash Flow Statement',
  'Notes to Accounts', "Auditor's Report", "Board's / Directors' Report",
  'CSR Report (if applicable)', 'AOC-2 — Related Party Transactions (if applicable)',
  'Consolidated Financial Statements (if applicable)',
]

export default function AttachmentsTable({ filing }) {
  const attachments = filing.attachments || []

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Paperclip className="size-4 text-muted-foreground" />
            Found in attachments/ folder
          </CardTitle>
          {attachments.length > 0 && (
            <CardAction>
              <Badge variant="secondary">{attachments.length}</Badge>
            </CardAction>
          )}
        </CardHeader>
        <CardContent>
          {attachments.length === 0 ? (
            <p className="text-sm text-amber-600 dark:text-amber-400 flex items-center gap-2">
              <FileWarning className="size-4" />
              No attachment files found — check the attachments/ folder for this client.
            </p>
          ) : (
            <div className="space-y-1">
              {attachments.map((a, i) => (
                <div key={i} className="flex items-center justify-between text-sm py-1.5 border-b last:border-0">
                  <span className="font-mono">{a.name}</span>
                  <span className="text-xs text-muted-foreground">{(a.size_bytes / 1024).toFixed(0)} KB</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListChecks className="size-4 text-muted-foreground" />
            Typical AOC-4 attachments
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground mb-2">Confirm applicability yourself — not all apply to every filing.</p>
          <ul className="text-sm space-y-1.5 list-disc list-inside marker:text-muted-foreground">
            {CHECKLIST.map(item => <li key={item}>{item}</li>)}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
