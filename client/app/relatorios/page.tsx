import { AuthedShell } from '@/components/authed-shell'
import { ReportsList } from '@/components/reports-list'

export default function RelatoriosPage() {
  return (
    <AuthedShell>
      <ReportsList />
    </AuthedShell>
  )
}
