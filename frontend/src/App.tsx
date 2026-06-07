import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { PublicRoute } from '@/components/PublicRoute'
import { Login } from '@/pages/Login'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          }
        />
        <Route path="/" element={<Navigate to="/chats" replace />} />
        <Route path="*" element={<Navigate to="/chats" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App