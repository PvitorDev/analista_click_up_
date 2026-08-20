import { AuthedShell } from '@/components/authed-shell'
import { ReportDetail } from '@/components/report-detail'

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return (
    <AuthedShell>
      <ReportDetail id={id} />
    </AuthedShell>
  )
}
