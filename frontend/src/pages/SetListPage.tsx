import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchCards, fetchScryfallSet, type CardMeta, type ScryfallSet } from '../api'

type SearchMode = 'card' | 'set'

type SetGroup = {
  code: string
  cards: CardMeta[]
  setInfo: ScryfallSet | null
}

export default function SetListPage() {
  const [cards, setCards] = useState<CardMeta[]>([])
  const [setInfoMap, setSetInfoMap] = useState<Record<string, ScryfallSet | null>>({})
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [searchMode, setSearchMode] = useState<SearchMode>('card')
  const navigate = useNavigate()

  useEffect(() => {
    fetchCards()
      .then(async (allCards) => {
        setCards(allCards)
        const codes = [...new Set(allCards.map((c) => c.latest_set_code).filter(Boolean))]
        const entries = await Promise.all(
          codes.map(async (code) => [code, await fetchScryfallSet(code)] as const),
        )
        setSetInfoMap(Object.fromEntries(entries))
      })
      .finally(() => setLoading(false))
  }, [])

  const filteredCards = useMemo<CardMeta[]>(() => {
    if (searchMode !== 'card' || query === '') return []
    const q = query.toLowerCase()
    return cards.filter(
      (c) =>
        c.card_name_en.toLowerCase().replace(/\+/g, ' ').includes(q) ||
        c.card_name_ja.includes(query),
    )
  }, [cards, query, searchMode])

  const setGroups = useMemo<SetGroup[]>(() => {
    const map = new Map<string, CardMeta[]>()
    for (const card of cards) {
      const code = card.latest_set_code || '??'
      if (!map.has(code)) map.set(code, [])
      map.get(code)!.push(card)
    }
    return [...map.entries()]
      .map(([code, grpCards]) => ({ code, cards: grpCards, setInfo: setInfoMap[code] ?? null }))
      .sort((a, b) => {
        const da = a.setInfo?.released_at ?? '0000-00-00'
        const db = b.setInfo?.released_at ?? '0000-00-00'
        return db.localeCompare(da)
      })
      .filter(
        (g) =>
          searchMode !== 'set' ||
          query === '' ||
          g.code.toLowerCase().includes(query.toLowerCase()) ||
          (g.setInfo?.name ?? '').toLowerCase().includes(query.toLowerCase()),
      )
  }, [cards, setInfoMap, query, searchMode])

  const showCardResults = searchMode === 'card' && query !== ''

  return (
    <div className="min-h-screen bg-mtg-bg text-mtg-text">
      <div className="border-b border-mtg-border bg-mtg-surface px-6 py-6">
        <h1 className="text-3xl font-bold text-mtg-gold tracking-wide">MTG Price Tracker</h1>
        <p className="text-mtg-muted text-sm mt-1">エキスパンション別 最安値検索</p>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Search bar + radio */}
        <div className="mb-6">
          <input
            type="search"
            placeholder={searchMode === 'card' ? 'カード名で検索（日本語・英語）...' : 'エキスパンション名で絞り込み...'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-mtg-surface border border-mtg-border rounded-lg px-4 py-3 text-mtg-text placeholder:text-mtg-muted focus:outline-none focus:border-mtg-gold mb-3"
          />
          <div className="flex gap-5">
            {(['card', 'set'] as const).map((mode) => (
              <label key={mode} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="radio"
                  name="searchMode"
                  value={mode}
                  checked={searchMode === mode}
                  onChange={() => { setSearchMode(mode); setQuery('') }}
                  className="accent-mtg-gold w-4 h-4"
                />
                <span className={`text-sm ${searchMode === mode ? 'text-mtg-gold' : 'text-mtg-muted'}`}>
                  {mode === 'card' ? 'カード名' : 'エキスパンション'}
                </span>
              </label>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48 text-mtg-muted">読み込み中...</div>
        ) : showCardResults ? (
          /* カード名検索結果 */
          filteredCards.length === 0 ? (
            <p className="text-mtg-muted text-center py-16">"{query}" に一致するカードが見つかりませんでした。</p>
          ) : (
            <ul className="space-y-1">
              {filteredCards.map((card) => (
                <li key={card.card_name_en}>
                  <button
                    onClick={() => navigate(`/prices/${encodeURIComponent(card.card_name_en)}`, { state: { card } })}
                    className="w-full flex items-center gap-4 bg-mtg-surface border border-mtg-border rounded-xl px-4 py-3 text-left hover:border-mtg-gold hover:bg-mtg-surface-2 transition-all duration-200 group cursor-pointer"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="font-semibold text-mtg-text group-hover:text-mtg-gold transition-colors">
                        {card.card_name_ja || card.card_name_en.replace(/\+/g, ' ')}
                      </span>
                      {card.card_name_ja && (
                        <span className="text-mtg-muted text-sm ml-3">
                          {card.card_name_en.replace(/\+/g, ' ')}
                        </span>
                      )}
                    </div>
                    <span className="text-xs font-mono text-mtg-muted shrink-0">{card.latest_set_code}</span>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : (
          /* エキスパンション一覧 */
          setGroups.length === 0 ? (
            <p className="text-mtg-muted text-center py-16">カードが登録されていません。</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              {setGroups.map((group) => (
                <button
                  key={group.code}
                  onClick={() => navigate(`/sets/${group.code}`)}
                  className="bg-mtg-surface border border-mtg-border rounded-xl p-4 text-left hover:border-mtg-gold hover:bg-mtg-surface-2 transition-all duration-200 group cursor-pointer"
                >
                  <div className="flex items-center gap-3 mb-3">
                    {group.setInfo?.icon_svg_uri ? (
                      <img
                        src={group.setInfo.icon_svg_uri}
                        alt={group.code}
                        className="w-8 h-8 opacity-60 group-hover:opacity-100 transition-opacity"
                        style={{ filter: 'invert(75%) sepia(60%) saturate(500%) hue-rotate(5deg)' }}
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-mtg-border flex items-center justify-center text-xs text-mtg-muted font-mono">
                        {group.code.slice(0, 2)}
                      </div>
                    )}
                    <span className="text-xs font-mono text-mtg-muted">{group.code}</span>
                  </div>

                  <p className="text-sm font-semibold text-mtg-text leading-snug mb-2 group-hover:text-mtg-gold transition-colors line-clamp-2">
                    {group.setInfo?.name ?? group.code}
                  </p>

                  <div className="flex items-center justify-between">
                    <span className="text-xs text-mtg-muted">
                      {group.setInfo?.released_at?.slice(0, 4) ?? ''}
                    </span>
                    <span className="text-xs bg-mtg-border rounded-full px-2 py-0.5 text-mtg-muted">
                      {group.cards.length}枚
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )
        )}
      </div>
    </div>
  )
}
