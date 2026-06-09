import { Routes, Route } from 'react-router-dom'
import CardSearchPage from './pages/CardSearchPage'
import PriceListPage from './pages/PriceListPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CardSearchPage />} />
      <Route path="/prices/:cardNameEn" element={<PriceListPage />} />
    </Routes>
  )
}
