import { Navigate, Route, Routes } from 'react-router'

import { ConfigurationShell } from './app/ConfigurationShell'
import { RunShell } from './app/RunShell'
import { HistoryPage } from './pages/HistoryPage'
import { ProductionPage } from './pages/ProductionPage'
import { SetupPage } from './pages/SetupPage'
import { SystemPage } from './pages/SystemPage'

export function App() {
  return (
    <Routes>
      <Route element={<Navigate replace to="/run" />} path="/" />
      <Route element={<RunShell />} path="/run">
        <Route element={<ProductionPage />} index />
        <Route element={<HistoryPage />} path="history" />
      </Route>
      <Route element={<ConfigurationShell />} path="/configuration">
        <Route element={<Navigate replace to="setup" />} index />
        <Route element={<SetupPage />} path="setup" />
        <Route element={<SystemPage />} path="system" />
      </Route>
      <Route element={<Navigate replace to="/run" />} path="*" />
    </Routes>
  )
}
