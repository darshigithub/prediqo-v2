import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import DataSourcesPage from './pages/DataSourcesPage'
import DatasetsPage from './pages/DatasetsPage'
import DatasetDetailPage from './pages/DatasetDetailPage'
import DataExplorerPage from './pages/DataExplorerPage'
import AnalystPage from './pages/AnalystPage'
import ChartBuilderPage from './pages/ChartBuilderPage'
import PredictionPage from './pages/PredictionPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/sources" element={<DataSourcesPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/datasets/:id" element={<DatasetDetailPage />} />
          <Route path="/explorer" element={<DataExplorerPage />} />
          <Route path="/analyst" element={<AnalystPage />} />
          <Route path="/charts" element={<ChartBuilderPage />} />
          <Route path="/prediction" element={<PredictionPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
