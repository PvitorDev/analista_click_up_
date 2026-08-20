import { AuthedShell } from '@/components/authed-shell'
import { TaskView } from '@/components/task-view'

export default async function TaskPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return (
    <AuthedShell>
      <TaskView id={id} />
    </AuthedShell>
  )
}
