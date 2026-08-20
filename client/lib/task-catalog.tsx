'use client'

import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { TaskRef } from './humanize'

interface CatalogValue {
  tasks: TaskRef[]
  byId: Map<string, TaskRef>
}

const TaskCatalogContext = createContext<CatalogValue>({
  tasks: [],
  byId: new Map(),
})

export function TaskCatalogProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = useState<TaskRef[]>([])

  useEffect(() => {
    api<TaskRef[]>('/api/task-catalog', { silent: true })
      .then(setTasks)
      .catch(() => setTasks([]))
  }, [])

  const byId = useMemo(() => {
    const m = new Map<string, TaskRef>()
    for (const t of tasks) {
      m.set(t.clickup_id, t)
      if (t.custom_id) m.set(t.custom_id, t)
    }
    return m
  }, [tasks])

  return (
    <TaskCatalogContext.Provider value={{ tasks, byId }}>
      {children}
    </TaskCatalogContext.Provider>
  )
}

export function useTaskCatalog(): CatalogValue {
  return useContext(TaskCatalogContext)
}

export function useTaskName(taskId: string, fallback?: string | null): string {
  const { byId } = useTaskCatalog()
  return fallback || byId.get(taskId)?.name || taskId
}
