import { AuthedShell } from '@/components/authed-shell'
import { LeaderboardView } from '@/components/leaderboard-view'

export default function LeaderboardPage() {
  return (
    <AuthedShell>
      <LeaderboardView />
    </AuthedShell>
  )
}
