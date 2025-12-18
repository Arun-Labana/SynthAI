import { useState, useCallback } from 'react'

const API_BASE = '/api/v1'

interface ApiResponse<T> {
  data: T | null
  error: string | null
  loading: boolean
}

interface Task {
  task_id: string
  status: string
  description?: string
  iteration_count?: number
  is_tests_passing?: boolean
  is_approved?: boolean
  pr_url?: string | null
  error_message?: string | null
  messages?: Array<{
    agent: string
    content: string
    timestamp: string
  }>
  code_files?: string[]
  test_files?: string[]
}

interface TaskListResponse {
  tasks: Task[]
  total: number
}

interface CodeFilesResponse {
  task_id: string
  code_files: Record<string, string>
  test_files: Record<string, string>
}

interface SpecResponse {
  task_id: string
  specification: string | null
  task_breakdown: Array<{
    id: string
    title: string
    description: string
    priority: string
    estimated_complexity: string
  }> | null
  acceptance_criteria: string[] | null
}

export function useApi() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const request = useCallback(async <T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T | null> => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const data = await response.json()
      return data as T
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Unknown error'
      setError(message)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  // Task operations
  const createTask = useCallback(async (
    taskDescription: string,
    targetRepoPath?: string,
    githubRepoUrl?: string,
    taskId?: string
  ) => {
    return request<{ task_id: string; status: string; message: string }>('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        task_description: taskDescription,
        target_repo_path: targetRepoPath,
        github_repo_url: githubRepoUrl,
        task_id: taskId,
      }),
    })
  }, [request])

  const getTask = useCallback(async (taskId: string) => {
    return request<Task>(`/tasks/${taskId}`)
  }, [request])

  const getTasks = useCallback(async () => {
    return request<TaskListResponse>('/tasks')
  }, [request])

  const approveTask = useCallback(async (taskId: string) => {
    return request<{ message: string }>(`/tasks/${taskId}/approve`, {
      method: 'POST',
    })
  }, [request])

  const rejectTask = useCallback(async (taskId: string, reason?: string) => {
    return request<{ message: string; task_id: string }>(`/tasks/${taskId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  }, [request])

  const getTaskCode = useCallback(async (taskId: string) => {
    return request<CodeFilesResponse>(`/tasks/${taskId}/code`)
  }, [request])

  const getTaskSpec = useCallback(async (taskId: string) => {
    return request<SpecResponse>(`/tasks/${taskId}/spec`)
  }, [request])

  // Health check
  const checkHealth = useCallback(async () => {
    return request<{
      api: string
      docker: string
      github: string
      docker_details?: Record<string, unknown>
      github_details?: Record<string, unknown>
    }>('/health')
  }, [request])

  // RAG operations
  const indexRepository = useCallback(async (repoPath: string, clearExisting = false) => {
    return request<{
      message: string
      repo_path: string
      chunks_indexed: number
    }>('/rag/index', {
      method: 'POST',
      body: JSON.stringify({
        repo_path: repoPath,
        clear_existing: clearExisting,
      }),
    })
  }, [request])

  const getRagStats = useCallback(async () => {
    return request<{
      total_chunks: number
      collection_name: string
      persist_directory: string
    }>('/rag/stats')
  }, [request])

  return {
    loading,
    error,
    createTask,
    getTask,
    getTasks,
    approveTask,
    rejectTask,
    getTaskCode,
    getTaskSpec,
    checkHealth,
    indexRepository,
    getRagStats,
  }
}

