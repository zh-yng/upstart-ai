import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

import { PrimeReactProvider } from 'primereact/api';

import "primereact/resources/themes/lara-dark-indigo/theme.css";
import "primereact/resources/primereact.min.css";
import "primeicons/primeicons.css";

const value = {
  ripple: true,
};

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <PrimeReactProvider value={value}>
      <App />
    </PrimeReactProvider>
  </StrictMode>,
)
