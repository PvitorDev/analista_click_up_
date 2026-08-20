import { AuthedShell } from '@/components/authed-shell'
import { ProfileView } from '@/components/profile-view'

export default async function PerfilPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return (
    <AuthedShell>
      <ProfileView id={id} />
    </AuthedShell>
  )
}
