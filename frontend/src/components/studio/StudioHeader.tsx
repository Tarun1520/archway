import { studioUi, studioViews, type StudioView } from '../../content/studio'
import { AccountMenu } from '../auth/AccountMenu'
import { MenuIcon, PlusIcon } from '../ui/icons'

interface StudioHeaderProps {
  status: string | null
  live: boolean
  view: StudioView
  onView: (view: StudioView) => void
  /** Opens the sidebar (only shown on screens too narrow to keep it open). */
  onMenu: () => void
  onNewProject: () => void
}

/**
 * The studio's nav bar: a rounded bar with the name on the left, the views as
 * a row of pills in the middle (the open one is white), and one white button on
 * the right to start a new project. The run's status sits beside that button.
 *
 * On a phone the pills move to their own row below and scroll sideways.
 */
export function StudioHeader({ status, live, view, onView, onMenu, onNewProject }: StudioHeaderProps) {
  return (
    <header className="flex flex-wrap items-center gap-x-16 gap-y-12 rounded-card border border-line bg-carbon/85 px-12 py-10 backdrop-blur-md md:px-20">
      <button
        type="button"
        onClick={onMenu}
        aria-label={studioUi.menu}
        className="flex size-40 items-center justify-center rounded-pill text-chalk hover:bg-soot focus-visible:outline-2 focus-visible:outline-vermilion lg:hidden"
      >
        <MenuIcon size={20} />
      </button>
      <a href="#" className="text-[18px] font-bold tracking-[-0.03em] text-chalk focus-visible:outline-2 focus-visible:outline-vermilion">
        Archway
      </a>

      {/* The views. A plain list of buttons: the open one is marked for screen readers with aria-current. */}
      <nav
        aria-label={studioUi.navLabel}
        className="order-last w-full overflow-x-auto [scrollbar-width:none] md:order-none md:mx-auto md:w-auto"
      >
        <ul className="flex w-max gap-2 rounded-pill border border-line bg-void/60 p-4">
          {studioViews.map((id) => (
            <li key={id}>
              <button
                type="button"
                onClick={() => onView(id)}
                aria-current={view === id ? 'page' : undefined}
                className={`h-36 rounded-pill px-14 text-[14px] whitespace-nowrap transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-vermilion lg:h-40 lg:px-18 lg:text-[15px] ${
                  view === id ? 'bg-chalk font-medium text-void' : 'text-chalk/80 hover:bg-soot hover:text-chalk'
                }`}
              >
                {studioUi.views[id]}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="ml-auto flex items-center gap-16 md:ml-0">
        {status && (
          <p className="hidden items-center gap-8 font-code text-label uppercase text-smoke xl:flex" aria-live="polite">
            <span aria-hidden="true" className={`inline-block size-8 rounded-pill ${live ? 'live-dot bg-vermilion' : 'bg-slate'}`} />
            {status}
          </p>
        )}
        <button
          type="button"
          onClick={onNewProject}
          className="flex h-40 items-center gap-6 rounded-pill bg-chalk px-18 text-[15px] font-semibold text-void transition-transform duration-150 hover:scale-[1.03] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-vermilion active:scale-[0.98] lg:h-44 lg:px-24"
        >
          <PlusIcon size={16} />
          {studioUi.newProject}
        </button>
        <AccountMenu />
      </div>
    </header>
  )
}
