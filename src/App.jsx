import { useState } from 'react'
import './App.css'

import { Button } from 'primereact/button';

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="App">
      <Button label="Heehee" icon="pi pi-check" />
    </div>
  )
}

export default App
