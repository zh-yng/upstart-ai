import { Routes, Route } from 'react-router';

import Landing from './routes/Landing.jsx';
import Dashboard from './routes/Dashboard.jsx';
import Download from './routes/Download.jsx';

function App() {

  return (
    <div className="App flex flex-column justify-content-center align-items-center" style={{ width: '100vw', height: '100vh', boxSizing: 'border-box' }}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/download" element={<Download />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="*" element={<div>404 not found. Were you looking for a different page?</div>} />
      </Routes>
    </div>
  )
}

export default App
