import { useCallback, useEffect, useRef, useState } from 'react'
import { createProject, addMessage, deleteProject, listProjects, renameProject } from '../lib/api/client'
import type { Project } from '../lib/api/types'
import { projectNameFromIdea, takePendingIdea } from '../lib/pendingIdea'

interface ProjectsState {
  projects: Project[]
  selectedId: string | null
  /** A message to show when loading or saving failed. Null when all is well. */
  problem: string | null
  loading: boolean
}

/**
 * Loads the saved projects from the backend, keeps track of which one is
 * selected, and creates new ones.
 *
 * On first load it also picks up an idea typed on the welcome page (if one is
 * waiting) and turns it into a project, with the idea as its first message.
 */
export function useProjects() {
  const [state, setState] = useState<ProjectsState>({
    projects: [],
    selectedId: null,
    problem: null,
    loading: true,
  })

  // In development React runs effects twice to catch mistakes. This flag makes
  // sure the first load (and the pending idea) is only handled once.
  const started = useRef(false)

  /** Makes a project (and selects it). Returns it, or null when it could not be saved. */
  const create = useCallback(async (name: string, idea: string | null): Promise<Project | null> => {
    try {
      const project = await createProject(name, idea)
      // The idea becomes the first chat message, so the conversation starts with it.
      if (idea) await addMessage(project.id, idea)
      setState((current) => ({
        ...current,
        projects: [project, ...current.projects],
        selectedId: project.id,
        problem: null,
      }))
      return project
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'unknown error'
      setState((current) => ({ ...current, problem: `The project could not be saved: ${reason}` }))
      return null
    }
  }, [])

  useEffect(() => {
    if (started.current) return
    started.current = true

    const load = async () => {
      try {
        const projects = await listProjects()
        setState({ projects, selectedId: projects[0]?.id ?? null, problem: null, loading: false })

        const idea = takePendingIdea()
        if (idea) await create(projectNameFromIdea(idea), idea)
      } catch (error) {
        const reason = error instanceof Error ? error.message : 'unknown error'
        setState({ projects: [], selectedId: null, problem: `Projects could not be loaded: ${reason}`, loading: false })
      }
    }
    void load()
  }, [create])

  const select = useCallback((projectId: string) => {
    setState((current) => ({ ...current, selectedId: projectId }))
  }, [])

  /** Deletes a project for good, then selects the next one in the list (if any). */
  const remove = useCallback(async (projectId: string) => {
    try {
      await deleteProject(projectId)
      setState((current) => {
        const projects = current.projects.filter((project) => project.id !== projectId)
        const selectedId = current.selectedId === projectId ? (projects[0]?.id ?? null) : current.selectedId
        return { ...current, projects, selectedId, problem: null }
      })
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'unknown error'
      setState((current) => ({ ...current, problem: `The project could not be deleted: ${reason}` }))
    }
  }, [])

  /** Gives a project a new name (the list shows it at once). A failure leaves the old name. */
  const rename = useCallback(async (projectId: string, name: string) => {
    try {
      const renamed = await renameProject(projectId, name)
      setState((current) => ({ ...current, projects: current.projects.map((project) => (project.id === projectId ? renamed : project)) }))
    } catch {
      // The old name stays; nothing else depends on it.
    }
  }, [])

  const selected = state.projects.find((project) => project.id === state.selectedId) ?? null

  return { ...state, selected, select, create, remove, rename }
}
