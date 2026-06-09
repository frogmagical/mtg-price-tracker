import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchPrices, type PriceItem } from '../api'

export default function PriceListPage() {
  const { cardNameEn } = useParams<{ cardNameEn: string }>()
  const [prices, setPrices] = useState<PriceItem[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    if (!cardNameEn) return
    setLoading(true)
    fetchPrices(cardNameEn)
      .then(setPrices)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [cardNameEn])

  const availablePrices = prices
    .filter((p) => p.stock != null && p.stock > 0)
    .sort((a, b) => a.price - b.price)

  return (
    <div style={{ padding: 16, maxWidth: 800, margin: '0 auto' }}>
      <button onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>← 戻る</button>
      <h2 style={{ fontSize: 18, marginBottom: 12 }}>
        {decodeURIComponent(cardNameEn ?? '').replace(/\+/g, ' ')}
      </h2>
      {loading ? (
        <p>読み込み中...</p>
      ) : availablePrices.length === 0 ? (
        <p>在庫ありの価格情報が見つかりませんでした。</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #333', textAlign: 'left' }}>
              <th style={{ padding: '8px 4px' }}>ショップ</th>
              <th style={{ padding: '8px 4px', textAlign: 'right' }}>価格</th>
              <th style={{ padding: '8px 4px', textAlign: 'center' }}>セット</th>
              <th style={{ padding: '8px 4px', textAlign: 'center' }}>言語</th>
              <th style={{ padding: '8px 4px', textAlign: 'center' }}>状態</th>
              <th style={{ padding: '8px 4px', textAlign: 'center' }}>在庫</th>
            </tr>
          </thead>
          <tbody>
            {availablePrices.map((p) => (
                <tr key={p.price_id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '8px 4px' }}>{p.shop}</td>
                  <td style={{ padding: '8px 4px', textAlign: 'right' }}>
                    ¥{p.price.toLocaleString()}
                    {p.foil && <span style={{ color: '#b8860b', marginLeft: 4, fontSize: 11 }}>FOIL</span>}
                    {p.promo && <span style={{ color: '#6a0dad', marginLeft: 4, fontSize: 11 }}>Promo</span>}
                  </td>
                  <td style={{ padding: '8px 4px', textAlign: 'center' }}>{p.set_code}</td>
                  <td style={{ padding: '8px 4px', textAlign: 'center' }}>{p.language}</td>
                  <td style={{ padding: '8px 4px', textAlign: 'center' }}>{p.condition}</td>
                  <td style={{ padding: '8px 4px', textAlign: 'center' }}>
                    {p.stock != null ? `${p.stock}枚` : 'なし'}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
