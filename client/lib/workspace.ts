export const WORKSPACE_STORAGE_KEY = 'analyst_workspace_id'

export function readStoredWorkspaceId(): string | null {
  try {
    return localStorage.getItem(WORKSPACE_STORAGE_KEY)
  } catch {
    return null
  }
}

export function writeStoredWorkspaceId(id: string) {
  try {
    localStorage.setItem(WORKSPACE_STORAGE_KEY, id)
  } catch {
    /* ignore quota / private mode */
  }
}
