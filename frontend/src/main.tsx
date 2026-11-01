// The entry point: the first file the browser runs (index.html points here).
// It loads the global styles and puts the React app into the page.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import './styles/index.css'

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('index.html is missing the <div id="root"> element.')
}

createRoot(rootElement).render(
  // StrictMode adds extra checks while developing. It has no effect in the built app.
  <StrictMode>
    <App />
  </StrictMode>,
)
