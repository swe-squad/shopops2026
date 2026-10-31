import { useState } from 'react'
import { API_BASE_URL } from './config'

function App() {
  const [count, setCount] = useState(0)

  return (
    <main>
      <h1>__SERVICE_NAME__</h1>
      <p>API: {API_BASE_URL || '/api (same-origin proxy)'}</p>
      <button type="button" onClick={() => setCount((c) => c + 1)}>
        Count is {count}
      </button>
    </main>
  )
}

export default App
