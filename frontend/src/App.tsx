import { Navigate, Route, Routes } from 'react-router'

import { ConfigurationShell } from './app/ConfigurationShell'
import { RunShell } from './app/RunShell'
import { HistoryPage } from './pages/HistoryPage'
import { ModelLibraryPage } from './pages/ModelLibraryPage'
import { PipelinePage } from './pages/PipelinePage'
import { ProductionPage } from './pages/ProductionPage'
import { SystemPage } from './pages/SystemPage'
import { ValidationPage } from './pages/ValidationPage'

export function App() {
  return (
    <Routes>
      <Route element={<Navigate replace to="/run" />} path="/" />
      <Route element={<RunShell />} path="/run">
        <Route element={<ProductionPage />} index />
        <Route element={<HistoryPage />} path="history" />
      </Route>
      <Route element={<ConfigurationShell />} path="/configuration">
        <Route element={<Navigate replace to="pipelines" />} index />
        <Route element={<PipelinePage />} path="pipelines" />
        <Route element={<ModelLibraryPage />} path="models" />
        <Route element={<ValidationPage />} path="validation" />
        <Route element={<Navigate replace to="../pipelines" />} path="setup" />
        <Route element={<SystemPage />} path="system" />
      </Route>
      <Route element={<Navigate replace to="/run" />} path="*" />
    </Routes>
  )
}
