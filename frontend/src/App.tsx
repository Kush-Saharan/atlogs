import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/AppShell'
import { Home } from '@/pages/Home'
import { KnowledgeGraph } from '@/pages/KnowledgeGraph'
import { AskCopilot } from '@/pages/AskCopilot'
import { Workflows } from '@/pages/Workflows'
import { Connectors } from '@/pages/Connectors'
import { Rca } from '@/pages/workflows/Rca'
import { Compliance } from '@/pages/workflows/Compliance'
import { Documents } from '@/pages/workflows/Documents'
import { Assets } from '@/pages/Assets'
import { Review } from '@/pages/Review'
import { Login } from '@/pages/Login'
import { Users } from '@/pages/Users'
import { Logs } from '@/pages/Logs'
import { RequireAuth } from '@/lib/auth'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<RequireAuth><AppShell>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/graph" element={<KnowledgeGraph />} />
          <Route path="/ask" element={<AskCopilot />} />
          <Route path="/workflows" element={<Workflows />} />
          <Route path="/connectors" element={<Connectors />} />
          <Route path="/workflows/ingest" element={<Navigate to="/connectors" replace />} />
          <Route path="/workflows/documents" element={<Documents />} />
          <Route path="/workflows/rca" element={<Rca />} />
          <Route path="/workflows/compliance" element={<Compliance />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/review" element={<Review />} />
          <Route path="/admin/users" element={<RequireAuth roles={['admin']}><Users /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </AppShell></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
