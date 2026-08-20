'use client'

import { createContext, useContext } from 'react'
import type { Me, Person } from './types'

interface MeContextValue {
  me: Me
  people: Person[]
}

const MeContext = createContext<MeContextValue | null>(null)

export function MeProvider({
  me,
  people,
  children,
}: {
  me: Me
  people: Person[]
  children: React.ReactNode
}) {
  return <MeContext.Provider value={{ me, people }}>{children}</MeContext.Provider>
}

export function useMe(): MeContextValue {
  const ctx = useContext(MeContext)
  if (!ctx) throw new Error('useMe deve ser usado dentro de MeProvider')
  return ctx
}
