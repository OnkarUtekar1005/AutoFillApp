import { CheckCircle2, AlertTriangle, FileWarning } from 'lucide-react'

export const STATUS_META = {
  Ready: {
    icon: CheckCircle2,
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/25',
    dot: 'bg-emerald-500',
    iconText: 'text-emerald-500',
  },
  'Needs Attention': {
    icon: AlertTriangle,
    badge: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/25',
    dot: 'bg-red-500',
    iconText: 'text-red-500',
  },
  'Missing Attachments': {
    icon: FileWarning,
    badge: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/25',
    dot: 'bg-amber-500',
    iconText: 'text-amber-500',
  },
}

export function statusMeta(status) {
  return STATUS_META[status] || STATUS_META['Needs Attention']
}
