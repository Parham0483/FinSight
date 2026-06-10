import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './store/authContext'
import { MascotProvider } from './store/mascotContext'
import App from './App'
import './styles/variables.css'
import './styles/global.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <MascotProvider>
          <App />
        </MascotProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
