import { useState, useMemo } from 'react'
import { Loader2, Save, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/**
 * Editable form for the MANUAL fields (not in any document — the CS fills these).
 * Values save per client and are reused automatically on every future extraction.
 *
 * props:
 *   filing         — the client's extraction result (for current values)
 *   manualFields   — [{key,label,section,data_type,enum_values}] where source==MANUAL
 *   sections       — {sectionKey: label}
 *   onSave(values) — persists {key: value}; returns a promise
 */
export default function ManualEntryForm({ filing, manualFields, sections, onSave }) {
  const initial = useMemo(() => {
    const o = {}
    for (const f of manualFields) o[f.key] = filing.fields?.[f.key]?.value ?? ''
    return o
  }, [manualFields, filing])

  const [values, setValues] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  const grouped = useMemo(() => {
    const g = {}
    for (const f of manualFields) {
      ;(g[f.section] ||= []).push(f)
    }
    return g
  }, [manualFields])

  function set(key, v) {
    setValues(prev => ({ ...prev, [key]: v }))
    setSaved(false)
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      // Only send non-empty values (never wipe saved ones with blanks).
      const payload = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== '' && v != null))
      await onSave(payload)
      setSaved(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const filledCount = Object.values(values).filter(v => v !== '' && v != null).length

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <p className="text-sm text-muted-foreground">
          These fields aren't in any document — fill them once and they're reused automatically for this client every year.
          <span className="ml-1 font-medium text-foreground">{filledCount}/{manualFields.length} filled.</span>
        </p>
        <div className="flex items-center gap-2">
          {error && <span className="text-sm text-red-600 dark:text-red-400">{error}</span>}
          <Button onClick={save} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : saved ? <Check /> : <Save />}
            {saved ? 'Saved' : 'Save manual fields'}
          </Button>
        </div>
      </div>

      {Object.entries(grouped).map(([sectionKey, fields]) => (
        <div key={sectionKey} className="rounded-lg border overflow-hidden">
          <div className="px-4 py-2.5 bg-muted/40 font-medium text-sm">{sections[sectionKey] || sectionKey}</div>
          <div className="p-4 grid sm:grid-cols-2 gap-4">
            {fields.map(f => (
              <div key={f.key} className="grid gap-1.5">
                <Label htmlFor={`m-${f.key}`} className="text-xs">{f.label}</Label>
                <FieldInput field={f} value={values[f.key] ?? ''} onChange={v => set(f.key, v)} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function FieldInput({ field, value, onChange }) {
  const id = `m-${field.key}`
  if (field.data_type === 'boolean') {
    return (
      <select id={id} value={value} onChange={e => onChange(e.target.value)}
        className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs focus-visible:ring-2 focus-visible:ring-ring/50 outline-none">
        <option value="">—</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </select>
    )
  }
  if (field.data_type === 'enum' && field.enum_values?.length) {
    return (
      <select id={id} value={value} onChange={e => onChange(e.target.value)}
        className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs focus-visible:ring-2 focus-visible:ring-ring/50 outline-none">
        <option value="">—</option>
        {field.enum_values.map(v => <option key={v} value={v}>{v}</option>)}
      </select>
    )
  }
  return (
    <Input
      id={id}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={field.data_type === 'date' ? 'YYYY-MM-DD' : field.data_type === 'numeric' ? '0' : ''}
      className="h-9"
    />
  )
}
