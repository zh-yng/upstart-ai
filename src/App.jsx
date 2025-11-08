import { useState } from 'react'

import { Button } from 'primereact/button';
import { Menubar } from 'primereact/menubar';
import { Routes, Route } from 'react-router';

import Landing from './routes/Landing.jsx';

function App() {

  return (
    <div className="App flex flex-column justify-content-center align-items-center" style={{ width: '100vw', height: '100vh', boxSizing: 'border-box' }}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/features" element={<div>Features</div>} />
        <Route path="*" element={<div>404 not found. Were you looking for a different apge?</div>} />
      </Routes>
    </div>
  )
}

export default App
