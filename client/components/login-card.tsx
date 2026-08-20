'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api, goToLogin } from '@/lib/api'
import type { Me } from '@/lib/types'
import { ClickUpMark, ClickUpWordmark } from './clickup-logo'
import { Spinner } from './primitives'

export function LoginCard() {
  const router = useRouter()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    // If a session already exists, go straight to the dashboard.
    let active = true
    api<Me>('/auth/me', { silent: true })
      .then(() => {
        if (active) router.replace('/')
      })
      .catch(() => {
        if (active) setChecking(false)
      })
    return () => {
      active = false
    }
  }, [router])

  return (
    <main className="flex min-h-svh items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-chrome p-10 text-center">
        <div className="mb-6 flex flex-col items-center gap-3">
          <ClickUpMark className="h-12 w-12" />
          <ClickUpWordmark className="text-xl" />
        </div>
        <h1 className="text-balance text-lg font-semibold text-foreground">
          Analista · gestão de tarefas
        </h1>
        <p className="mt-2 text-pretty text-sm text-muted-foreground">
          Diagnóstico do board a partir dos dados do ClickUp.
        </p>

        <button
          type="button"
          onClick={goToLogin}
          disabled={checking}
          className="mt-8 flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {checking ? <Spinner /> : null}
          Entrar
        </button>
      </div>
    </main>
  )
}
