import { Routes, Route } from 'react-router-dom'
import CardStoreProvider from './components/CardStoreProvider'
import SetListPage from './pages/SetListPage'
import CardListPage from './pages/CardListPage'
import PriceListPage from './pages/PriceListPage'

export default function App() {
  return (
    <CardStoreProvider>
      <Routes>
        <Route path="/" element={<SetListPage />} />
        <Route path="/sets/:setCode" element={<CardListPage />} />
        <Route path="/prices/:cardNameEn" element={<PriceListPage />} />
      </Routes>
    </CardStoreProvider>
  )
}
