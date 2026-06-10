import { useState, useEffect, type ReactNode } from 'react'
import { fetchCards, fetchScryfallSet, type CardMeta, type ScryfallSet } from '../api'
import {
  CardStoreContext,
  readCache, writeCache,
  CARDS_KEY, SET_INFO_KEY, CARDS_TTL_MS, SET_INFO_TTL_MS,
} from '../hooks/useCardStore'

export default function CardStoreProvider({ children }: { children: ReactNode }) {
  const [cards, setCards] = useState<CardMeta[]>(() => readCache<CardMeta[]>(CARDS_KEY) ?? [])
  const [setInfoMap, setSetInfoMap] = useState<Record<string, ScryfallSet | null>>(
    () => readCache<Record<string, ScryfallSet | null>>(SET_INFO_KEY) ?? {},
  )
  const [loading, setLoading] = useState(() => {
    const cached = readCache<CardMeta[]>(CARDS_KEY)
    return cached === null
  })

  useEffect(() => {
    const cachedCards = readCache<CardMeta[]>(CARDS_KEY)
    const cachedSets = readCache<Record<string, ScryfallSet | null>>(SET_INFO_KEY)

    if (cachedCards && cachedSets) {
      // キャッシュ有効: 即時反映済み（初期stateで設定済み）
      setLoading(false)
      return
    }

    // キャッシュなし or TTL切れ: 取得
    fetchCards()
      .then(async (allCards) => {
        writeCache(CARDS_KEY, allCards, CARDS_TTL_MS)
        setCards(allCards)

        // セット情報: キャッシュ有効なものはスキップ
        const existingSets = cachedSets ?? setInfoMap
        const codes = [...new Set(allCards.map((c) => c.latest_set_code).filter(Boolean))]
        const missing = codes.filter((code) => !(code in existingSets))

        const newEntries = await Promise.all(
          missing.map(async (code) => [code, await fetchScryfallSet(code)] as const),
        )
        const merged = { ...existingSets, ...Object.fromEntries(newEntries) }
        writeCache(SET_INFO_KEY, merged, SET_INFO_TTL_MS)
        setSetInfoMap(merged)
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <CardStoreContext.Provider value={{ cards, setInfoMap, loading }}>
      {children}
    </CardStoreContext.Provider>
  )
}
