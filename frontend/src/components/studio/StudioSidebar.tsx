import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { stages, studioUi, type StageId } from '../../content/studio'
import type { Project } from '../../lib/api/types'
import {
  CheckIcon, ChevronIcon, DocumentIcon, FolderIcon, IdeaIcon, ListCheckIcon, OptionsIcon, PlanIcon, PlusIcon, QuestionIcon, SearchIcon, SidebarIcon, TrashIcon,
} from '../ui/icons'

interface StudioSidebarProps {
  projects: Project[]
  selectedId: string | null
  loading: boolean
  /** The step the open project is on, or null when no project is open. */
  stage: StageId | null
  /** Whether the "new project" field is open (the nav bar's button opens it too). */
  creating: boolean
  onCreating: (open: boolean) => void
  /** Folded: only a slim rail of icons is shown. */
  collapsed: boolean
  /** The button at the top: folds the sidebar (or, in the phone drawer, closes it). */
  onToggle: () => void
  toggleLabel: string
  /** The step on screen (a passed one when the user looks back). */
  shown: StageId | null
  /** Opens a step: the current one, or a passed one to look back at. */
  onStep: (stage: StageId) => void
  onSelect: (projectId: string) => void
  onCreate: (name: string) => void
  onDelete: (projectId: string) => void
}

const STEP_ICONS: Record<StageId, ReactNode> = {
  idea: <IdeaIcon size={20} />,
  questions: <QuestionIcon size={20} />,
  brief: <DocumentIcon size={20} />,
  research: <SearchIcon size={20} />,
  shortlist: <ListCheckIcon size={20} />,
  options: <OptionsIcon size={20} />,
  plan: <PlanIcon size={20} />,
}

/**
 * The sidebar: Archway's mark and name at the top, the seven steps (done, now,
 * still to come), and a folding group with every project (each with a delete
 * button) and a way to start a new one.
 *
 * The button at its top folds it into a slim rail of icons, giving the content
 * more room; the same button opens it again. Folded, the rail still shows the
 * steps, and its projects and "+" buttons open the sidebar where they lead.
 */
export function StudioSidebar(props: StudioSidebarProps) {
  const { projects, selectedId, loading, stage, creating, onCreating, collapsed, onToggle, toggleLabel } = props
  const [projectsOpen, setProjectsOpen] = useState(true)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const current = stage ? stages.findIndex((s) => s.id === stage) : -1

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    props.onCreate(trimmed)
    setName('')
    onCreating(false)
  }

  const initial = (
    <span aria-hidden="true" className="flex size-32 shrink-0 items-center justify-center rounded-default bg-chalk text-[15px] font-bold text-void">
      A
    </span>
  )
  const toggle = (
    <button
      type="button"
      onClick={onToggle}
      aria-label={toggleLabel}
      title={toggleLabel}
      className="flex size-36 shrink-0 items-center justify-center rounded-control text-smoke transition-colors hover:bg-soot hover:text-chalk focus-visible:outline-2 focus-visible:outline-vermilion"
    >
      <SidebarIcon size={18} />
    </button>
  )
  const railButton = 'flex size-44 items-center justify-center rounded-control transition-colors focus-visible:outline-2 focus-visible:outline-vermilion'

  // Folded: a slim rail of icons. Each icon has a name for screen readers and a hover tip.
  if (collapsed) {
    return (
      <div className="flex h-full flex-col items-center gap-4 rounded-card border border-line bg-carbon/55 py-12">
        {toggle}
        <div className="mt-8 mb-16" title="Archway">{initial}</div>
        {stage &&
          stages.map((step, index) => (
            <button
              key={step.id}
              type="button"
              onClick={() => props.onStep(step.id)}
              disabled={index > current}
              aria-label={step.label}
              title={step.label}
              aria-current={step.id === props.shown ? 'step' : undefined}
              className={`${railButton} relative ${step.id === props.shown ? 'bg-soot text-chalk' : index <= current ? 'text-chalk/85 hover:bg-soot/60' : 'text-slate'}`}
            >
              {STEP_ICONS[step.id]}
              {index === current && <span aria-hidden="true" className="live-dot absolute top-8 right-8 size-6 rounded-pill bg-vermilion" />}
            </button>
          ))}
        <hr className="my-12 w-32 border-line" />
        <button
          type="button"
          onClick={() => {
            setProjectsOpen(true)
            onToggle()
          }}
          aria-label={studioUi.projects}
          title={studioUi.projects}
          className={`${railButton} text-chalk hover:bg-soot/60`}
        >
          <FolderIcon size={20} />
        </button>
        <button
          type="button"
          onClick={() => {
            setProjectsOpen(true)
            onCreating(true)
            onToggle()
          }}
          aria-label={studioUi.newProject}
          title={studioUi.newProject}
          className={`${railButton} text-smoke hover:bg-soot/60 hover:text-chalk`}
        >
          <PlusIcon size={20} />
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto rounded-card border border-line bg-carbon/55 p-16">
      {/* The app's mark and name, and the fold button. */}
      <div className="flex items-center gap-12 pl-8">
        {initial}
        <span className="min-w-0 flex-1 truncate text-[16px] font-medium text-chalk">Archway</span>
        {toggle}
      </div>

      {/* The steps. They show progress; clicking a passed one opens it again to look back at. Later ones cannot be opened yet. */}
      {stage && (
        <nav aria-label={studioUi.steps} className="mt-32">
          <ul className="flex flex-col gap-2">
            {stages.map((step, index) => {
              const done = index < current
              const now = index === current
              const onScreen = step.id === props.shown
              return (
                <li key={step.id}>
                  <button
                    type="button"
                    onClick={() => props.onStep(step.id)}
                    disabled={index > current}
                    aria-current={onScreen ? 'step' : undefined}
                    className={`flex h-44 w-full items-center gap-12 rounded-control px-10 text-left text-[16px] transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-vermilion ${
                      onScreen ? 'bg-soot text-chalk' : done || now ? 'text-chalk/85 hover:bg-soot/60' : 'text-slate'
                    }`}
                  >
                    <span className="shrink-0">{STEP_ICONS[step.id]}</span>
                    <span className="flex-1">{step.label}</span>
                    {now && <span aria-hidden="true" className="live-dot size-8 rounded-pill bg-vermilion" />}
                    {done && <span className="text-smoke"><CheckIcon size={16} /></span>}
                    <span className="sr-only">{now ? studioUi.stepNow : done ? studioUi.stepDone : ''}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>
      )}

      <hr className="mx-4 my-20 border-line" />

      {/* Projects: a group that folds away. */}
      <button
        type="button"
        onClick={() => setProjectsOpen(!projectsOpen)}
        aria-expanded={projectsOpen}
        aria-controls="sidebar-projects"
        className="flex h-44 w-full items-center gap-12 rounded-control px-10 text-left text-[16px] font-medium text-chalk hover:bg-soot/60 focus-visible:outline-2 focus-visible:outline-vermilion"
      >
        <FolderIcon size={20} />
        <span className="flex-1">{studioUi.projects}</span>
        <span className={`transition-transform duration-200 ${projectsOpen ? '' : 'rotate-180'}`}>
          <ChevronIcon size={16} />
        </span>
      </button>

      {projectsOpen && (
        <div id="sidebar-projects" className="mt-4 ml-20 min-h-0 flex-1 overflow-y-auto border-l border-line pl-8">
          {loading && <p className="px-10 py-8 text-[14px] text-smoke">{studioUi.loadingProjects}</p>}
          {!loading && projects.length === 0 && <p className="px-10 py-8 text-[14px] text-smoke">{studioUi.noProjects}</p>}

          <ul className="flex flex-col gap-2">
            {projects.map((project) => {
              const isSelected = project.id === selectedId
              return (
                <li key={project.id}>
                  <div className={`flex items-center rounded-control ${isSelected ? 'bg-soot' : 'hover:bg-soot/60'}`}>
                    <button
                      type="button"
                      onClick={() => props.onSelect(project.id)}
                      aria-current={isSelected ? 'true' : undefined}
                      className={`min-h-40 min-w-0 flex-1 truncate rounded-control px-10 text-left text-[15px] focus-visible:outline-2 focus-visible:outline-vermilion ${
                        isSelected ? 'font-medium text-chalk' : 'text-chalk/75 hover:text-chalk'
                      }`}
                    >
                      {project.name}
                    </button>
                    <button
                      type="button"
                      aria-label={`${studioUi.deleteProject}: ${project.name}`}
                      onClick={() => setConfirmingId(project.id)}
                      className="flex size-32 shrink-0 items-center justify-center rounded-control text-smoke transition-colors hover:bg-void/60 hover:text-vermilion focus-visible:outline-2 focus-visible:outline-vermilion"
                    >
                      <TrashIcon size={16} />
                    </button>
                  </div>

                  {/* Deleting cannot be undone, so the first click only asks. */}
                  {confirmingId === project.id && (
                    <div role="alertdialog" aria-label={studioUi.deleteAsk} className="my-4 rounded-control border border-line bg-void/60 p-12">
                      <p className="text-[13px] text-chalk">{studioUi.deleteAsk}</p>
                      <div className="mt-8 flex gap-12">
                        <button type="button" autoFocus onClick={() => setConfirmingId(null)} className="min-h-32 text-[13px] text-smoke hover:text-chalk">
                          {studioUi.cancel}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setConfirmingId(null)
                            props.onDelete(project.id)
                          }}
                          className="min-h-32 text-[13px] font-semibold text-vermilion"
                        >
                          {studioUi.deleteYes}
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>

          {creating ? (
            <form onSubmit={submit} className="mt-8 flex flex-col gap-8 px-2">
              <label htmlFor="sidebar-new-project" className="sr-only">{studioUi.newProjectName}</label>
              <input
                id="sidebar-new-project"
                value={name}
                onChange={(event) => setName(event.target.value)}
                onKeyDown={(event) => event.key === 'Escape' && onCreating(false)}
                placeholder={studioUi.newProjectName}
                maxLength={120}
                autoFocus
                className="h-40 rounded-control border border-line bg-void/60 px-12 text-[15px] text-chalk placeholder:text-smoke focus:border-chalk/40 focus:outline-none"
              />
              <div className="flex gap-12 px-2">
                <button type="submit" className="min-h-32 text-[14px] font-semibold text-chalk hover:text-vermilion">{studioUi.create}</button>
                <button type="button" onClick={() => onCreating(false)} className="min-h-32 text-[14px] text-smoke hover:text-chalk">
                  {studioUi.cancel}
                </button>
              </div>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => onCreating(true)}
              className="mt-4 flex min-h-40 w-full items-center gap-8 rounded-control px-10 text-[15px] text-smoke hover:bg-soot/60 hover:text-chalk focus-visible:outline-2 focus-visible:outline-vermilion"
            >
              <PlusIcon size={16} />
              {studioUi.newProject}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
