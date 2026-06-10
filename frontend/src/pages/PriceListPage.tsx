import { useEffect, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { fetchPrices, cardImageUrl, type PriceItem, type CardMeta } from '../api'

export default function PriceListPage() {
  const { cardNameEn } = useParams<{ cardNameEn: string }>()
  const location = useLocation()
  const cardMeta = (location.state as { card?: CardMeta } | null)?.card
  const [prices, setPrices] = useState<PriceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (!cardNameEn) return
    setLoading(true)
    setError('')
    fetchPrices(cardNameEn)
      .then(setPrices)
      .catch(() => setError('価格情報の取得に失敗しました。'))
      .finally(() => setLoading(false))
  }, [cardNameEn])

  const availablePrices = prices
    .filter((p) => p.stock != null && p.stock > 0)
    .sort((a, b) => a.price - b.price)

  const displayNameJa = cardMeta?.card_name_ja || ''
  const displayNameEn = decodeURIComponent(cardNameEn ?? '').replace(/\+/g, ' ')

  return (
    <div className="min-h-screen bg-mtg-bg text-mtg-text">
      {/* Art crop banner */}
      <div className="relative h-48 overflow-hidden bg-mtg-surface">
        {cardMeta && cardImageUrl(cardMeta) && (
          <img
            src={cardImageUrl(cardMeta)}
            alt=""
            className="w-full h-full object-cover opacity-50"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-mtg-bg via-mtg-bg/60 to-transparent" />
        <div className="absolute bottom-0 left-0 px-6 pb-4">
          <button
            onClick={() => navigate(-1)}
            className="text-mtg-muted hover:text-mtg-text text-sm mb-2 flex items-center gap-1 transition-colors"
          >
            ← 戻る
          </button>
          {displayNameJa && (
            <h1 className="text-2xl font-bold text-mtg-gold leading-tight">{displayNameJa}</h1>
          )}
          <p className={`text-sm ${displayNameJa ? 'text-mtg-muted' : 'text-2xl font-bold text-mtg-gold'}`}>
            {displayNameEn}
          </p>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-mtg-muted">読み込み中...</div>
        ) : error ? (
          <p className="text-red-400 text-center py-8">{error}</p>
        ) : availablePrices.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-mtg-muted">在庫ありの価格情報が見つかりませんでした。</p>
            <p className="text-mtg-muted text-xs mt-2">全{prices.length}件（在庫なし含む）</p>
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-3 mb-4">
              <span className="text-mtg-muted text-sm">最安値</span>
              <span className="text-2xl font-bold text-mtg-gold">
                ¥{availablePrices[0].price.toLocaleString()}
              </span>
              <span className="text-mtg-muted text-sm">{availablePrices[0].shop}</span>
            </div>

            <div className="border border-mtg-border rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-mtg-surface-2 text-mtg-muted text-xs">
                    <th className="text-left px-4 py-3">ショップ</th>
                    <th className="text-right px-4 py-3">価格</th>
                    <th className="text-center px-3 py-3">セット</th>
                    <th className="text-center px-3 py-3">言語</th>
                    <th className="text-center px-3 py-3">状態</th>
                    <th className="text-center px-3 py-3">在庫</th>
                  </tr>
                </thead>
                <tbody>
                  {availablePrices.map((p, i) => (
                    <tr
                      key={p.price_id}
                      className={`border-t border-mtg-border transition-colors hover:bg-mtg-surface-2 ${i === 0 ? 'bg-mtg-surface' : ''}`}
                    >
                      <td className="px-4 py-3 text-mtg-text">{p.shop}</td>
                      <td className="px-4 py-3 text-right font-semibold text-mtg-gold">
                        ¥{p.price.toLocaleString()}
                        {p.foil && (
                          <span className="ml-1.5 text-[10px] bg-amber-900/60 text-amber-300 px-1.5 py-0.5 rounded-full">
                            FOIL
                          </span>
                        )}
                        {p.promo && (
                          <span className="ml-1.5 text-[10px] bg-purple-900/60 text-purple-300 px-1.5 py-0.5 rounded-full">
                            Promo
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-center text-mtg-muted text-xs">{p.set_code}</td>
                      <td className="px-3 py-3 text-center text-mtg-muted text-xs">{p.language}</td>
                      <td className="px-3 py-3 text-center text-mtg-muted text-xs">{p.condition}</td>
                      <td className="px-3 py-3 text-center text-mtg-muted text-xs">
                        {p.stock != null ? `${p.stock}枚` : 'なし'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
