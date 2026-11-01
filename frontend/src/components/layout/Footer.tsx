import { footer, navLinks } from '../../content/welcome'
import { BrandMark } from '../ui/BrandMark'

/** The bottom of the page: brand, section links, and the tagline. Back to the hero's night colors. */
export function Footer() {
  return (
    <footer className="relative z-20 bg-onyx px-20 pt-56 pb-32 md:px-32">
      <div className="mx-auto max-w-page">
        <div className="flex flex-col gap-24 pt-8 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-8 text-ivory">
            <BrandMark size={20} />
            <span className="text-body-sm font-strong tracking-[0.22em] uppercase">Archway</span>
          </div>

          <ul className="flex flex-wrap gap-x-24">
            {navLinks.map((link) => (
              <li key={link.href}>
                <a href={link.href} // Tall enough to tap comfortably on a phone.
                  className="inline-flex min-h-44 items-center text-body-sm text-ash transition-colors duration-200 hover:text-ivory">
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </div>

        <p className="mt-32 text-caption text-ash">{footer.tagline}</p>
      </div>
    </footer>
  )
}
