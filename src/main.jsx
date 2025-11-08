import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

import { PrimeReactProvider } from 'primereact/api';
import { BrowserRouter } from 'react-router';

import "primereact/resources/themes/lara-light-indigo/theme.css";
import "primereact/resources/primereact.min.css";
import "primeicons/primeicons.css";
import 'primeflex/primeflex.css';

const value = {
  ripple: true,
};

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <PrimeReactProvider value={value}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </PrimeReactProvider>
  </StrictMode>,
)
