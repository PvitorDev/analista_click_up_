import { AuthedShell } from '@/components/authed-shell'
import { HomeDashboard } from '@/components/home-dashboard'

export default function HomePage() {
  return (
    <AuthedShell>
      <HomeDashboard />
    </AuthedShell>
  )
}
