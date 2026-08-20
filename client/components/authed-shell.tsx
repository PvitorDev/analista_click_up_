'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import type { Me, Person } from '@/lib/types'
import { MeProvider } from '@/lib/me-context'
import { TaskCatalogProvider } from '@/lib/task-catalog'
import { Shell } from './shell'
import { ChatWidget } from './chat-widget'
import { GenerateReportProvider } from './generate-button'
import { PageLoader } from './primitives'

/**
 * Client guard + chrome for every authenticated page.
 * Loads /auth/me (redirects to /login on 401) and /api/people (admin shell),
 * then renders the Shell, the page content, and the chat FAB.
 */
export function AuthedShell({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [me, setMe] = useState<Me | null>(null)
  const [people, setPeople] = useState<Person[]>([])
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const meRes = await api<Me>('/auth/me', { silent: true })
        if (!active) return
        setMe(meRes)
        try {
          const p = await api<Person[]>('/api/people', { silent: true })
          if (active) setPeople(p)
        } catch {
          /* non-fatal */
        }
        if (active) setReady(true)
      } catch {
        // api() already redirects to /login on 401
        router.replace('/login')
      }
    })()
    return () => {
      active = false
    }
  }, [router])

  if (!ready || !me) {
    return (
      <div className="min-h-svh bg-background">
        <PageLoader />
      </div>
    )
  }

  return (
    <MeProvider me={me} people={people}>
      <TaskCatalogProvider>
        <GenerateReportProvider>
          <div className="flex h-svh flex-col overflow-hidden">
            <Shell>{children}</Shell>
            <ChatWidget />
          </div>
        </GenerateReportProvider>
      </TaskCatalogProvider>
    </MeProvider>
  )
}
