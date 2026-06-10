import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchCards, fetchScryfallSet, scryfallCardImageUrl, type CardMeta, type ScryfallSet } from '../api'

export default function CardListPage() {
  const { setCode } = useParams<{ setCode: string }>()
  const [cards, setCards] = useState<CardMeta[]>([])
  const [setInfo, setSetInfo] = useState<ScryfallSet | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    if (!setCode) return
    Promise.all([fetchCards(), fetchScryfallSet(setCode)])
      .then(([allCards, info]) => {
        setCards(allCards.filter((c) => c.latest_set_code === setCode))
        setSetInfo(info)
      })
      .finally(() => setLoading(false))
  }, [setCode])

  return (
    <div className="min-h-screen bg-mtg-bg text-mtg-text">
      <div className="border-b border-mtg-border bg-mtg-surface px-6 py-4">
        <button
          onClick={() => navigate('/')}
          className="text-mtg-muted hover:text-mtg-text text-sm mb-3 flex items-center gap-1 transition-colors"
        >
          ← エキスパンション一覧
        </button>
        <div className="flex items-center gap-3">
          {setInfo?.icon_svg_uri && (
            <img
              src={setInfo.icon_svg_uri}
              alt={setCode}
              className="w-9 h-9"
              style={{ filter: 'invert(75%) sepia(60%) saturate(500%) hue-rotate(5deg)' }}
            />
          )}
          <div>
            <h1 className="text-xl font-bold text-mtg-gold">{setInfo?.name ?? setCode}</h1>
            <p className="text-xs text-mtg-muted">
              {setInfo?.released_at?.slice(0, 4)}
              {setInfo?.released_at ? ' · ' : ''}
              {cards.length}枚登録
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {loading ? (
          <div className="flex items-center justify-center h-48 text-mtg-muted">読み込み中...</div>
        ) : cards.length === 0 ? (
          <p className="text-mtg-muted text-center py-16">このエキスパンションにカードが登録されていません。</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {cards.map((card) => (
              <button
                key={card.card_name_en}
                onClick={() =>
                  navigate(`/prices/${encodeURIComponent(card.card_name_en)}`, { state: { card } })
                }
                className="group rounded-xl overflow-hidden border border-mtg-border hover:border-mtg-gold transition-all duration-200 bg-mtg-surface cursor-pointer text-left"
              >
                <div className="aspect-[5/7] overflow-hidden bg-mtg-border relative">
                  <img
                    src={scryfallCardImageUrl(card.card_name_en, 'small')}
                    alt={card.card_name_ja || card.card_name_en}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    onError={(e) => {
                      const el = e.currentTarget
                      el.style.display = 'none'
                      el.parentElement!.classList.add('flex', 'items-center', 'justify-center')
                    }}
                  />
                  {card.cache_mode === 'lazy' && (
                    <span className="absolute top-1.5 right-1.5 text-[10px] bg-black/70 text-mtg-muted px-1.5 py-0.5 rounded-full">
                      旧
                    </span>
                  )}
                </div>
                <div className="p-2.5">
                  <p className="text-xs font-semibold text-mtg-text leading-tight truncate group-hover:text-mtg-gold transition-colors">
                    {card.card_name_ja || card.card_name_en.replace(/\+/g, ' ')}
                  </p>
                  <p className="text-[10px] text-mtg-muted truncate mt-0.5">
                    {card.card_name_en.replace(/\+/g, ' ')}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
