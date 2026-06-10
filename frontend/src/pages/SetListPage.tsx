import { useState, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CardMeta, ScryfallSet } from '../api'
import { useCardStore } from '../hooks/useCardStore'

type SearchMode = 'card' | 'set'

type SetGroup = {
  code: string
  cards: CardMeta[]
  setInfo: ScryfallSet | null
}

const MAX_SUGGESTIONS = 10

export default function SetListPage() {
  const { cards, setInfoMap, loading } = useCardStore()
  const [query, setQuery] = useState('')
  const [searchMode, setSearchMode] = useState<SearchMode>('card')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const suggestions = useMemo<CardMeta[]>(() => {
    if (searchMode !== 'card' || query.trim() === '') return []
    const q = query.toLowerCase()
    return cards
      .filter(
        (c) =>
          c.card_name_en.toLowerCase().replace(/\+/g, ' ').includes(q) ||
          c.card_name_ja.includes(query),
      )
      .slice(0, MAX_SUGGESTIONS)
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

  const goToCard = (card: CardMeta) => {
    setQuery('')
    setShowSuggestions(false)
    setActiveIndex(-1)
    navigate(`/prices/${encodeURIComponent(card.card_name_en)}`, { state: { card } })
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault()
      goToCard(suggestions[activeIndex])
    } else if (e.key === 'Escape') {
      setShowSuggestions(false)
      setActiveIndex(-1)
    }
  }

  return (
    <div className="min-h-screen bg-mtg-bg text-mtg-text" onClick={() => setShowSuggestions(false)}>
      <div className="border-b border-mtg-border bg-mtg-surface px-6 py-6">
        <h1 className="text-3xl font-bold text-mtg-gold tracking-wide">MTG Price Tracker</h1>
        <p className="text-mtg-muted text-sm mt-1">エキスパンション別 最安値検索</p>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="mb-6">
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <input
              ref={inputRef}
              type="search"
              placeholder={searchMode === 'card' ? 'カード名で検索（日本語・英語）...' : 'エキスパンション名で絞り込み...'}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setShowSuggestions(true)
                setActiveIndex(-1)
              }}
              onFocus={() => query && setShowSuggestions(true)}
              onKeyDown={handleKeyDown}
              className="w-full bg-mtg-surface border border-mtg-border rounded-lg px-4 py-3 text-mtg-text placeholder:text-mtg-muted focus:outline-none focus:border-mtg-gold"
            />

            {searchMode === 'card' && showSuggestions && suggestions.length > 0 && (
              <ul className="absolute z-50 w-full mt-1 bg-mtg-surface border border-mtg-border rounded-xl overflow-hidden shadow-xl">
                {suggestions.map((card, i) => (
                  <li key={card.card_name_en}>
                    <button
                      onMouseDown={(e) => { e.preventDefault(); goToCard(card) }}
                      className={`w-full flex items-center justify-between px-4 py-3 text-left transition-colors cursor-pointer ${
                        i === activeIndex
                          ? 'bg-mtg-surface-2 text-mtg-gold'
                          : 'hover:bg-mtg-surface-2 text-mtg-text'
                      } ${i !== 0 ? 'border-t border-mtg-border' : ''}`}
                    >
                      <span>
                        <span className="font-semibold">
                          {card.card_name_ja || card.card_name_en.replace(/\+/g, ' ')}
                        </span>
                        {card.card_name_ja && (
                          <span className="text-mtg-muted text-sm ml-3">
                            {card.card_name_en.replace(/\+/g, ' ')}
                          </span>
                        )}
                      </span>
                      <span className="text-xs font-mono text-mtg-muted shrink-0 ml-3">
                        {card.latest_set_code}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex gap-5 mt-3">
            {(['card', 'set'] as const).map((mode) => (
              <label key={mode} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="radio"
                  name="searchMode"
                  value={mode}
                  checked={searchMode === mode}
                  onChange={() => { setSearchMode(mode); setQuery(''); setShowSuggestions(false) }}
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
        ) : setGroups.length === 0 ? (
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
        )}
      </div>
    </div>
  )
}
