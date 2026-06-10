import { Routes, Route } from 'react-router-dom'
import SetListPage from './pages/SetListPage'
import CardListPage from './pages/CardListPage'
import PriceListPage from './pages/PriceListPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SetListPage />} />
      <Route path="/sets/:setCode" element={<CardListPage />} />
      <Route path="/prices/:cardNameEn" element={<PriceListPage />} />
    </Routes>
  )
}
