import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client' // ✅ using createRoot
import './index.css'
import App from './App.jsx'

import { BranchProvider } from './context/BranchContext'

const root = createRoot(document.getElementById('root')) // ✅ use createRoot
root.render(
  <StrictMode>
    <BranchProvider>
      <App />
    </BranchProvider>
  </StrictMode>
)