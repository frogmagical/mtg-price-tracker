const BASE_URL = import.meta.env.VITE_API_ENDPOINT ?? ''

export type PriceItem = {
  price_id: string
  shop: string
  price: number
  set_code: string
  language: string
  stock?: number
  condition: string
  foil: boolean
  promo: boolean
  played: boolean
  updated_at: string
  fetched_at: string
}

export type CardMeta = {
  card_name_en: string
  card_name_ja: string
  cache_mode: 'scheduled' | 'lazy'
  latest_set_code: string
}

export async function fetchPrices(cardNameEn: string): Promise<PriceItem[]> {
  const res = await fetch(`${BASE_URL}/prices/${encodeURIComponent(cardNameEn)}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return data.prices as PriceItem[]
}

export async function fetchCards(): Promise<CardMeta[]> {
  const res = await fetch(`${BASE_URL}/cards`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return data.cards as CardMeta[]
}

export async function addCard(params: {
  card_name_en: string
  card_name_ja?: string
  latest_set_code?: string
  latest_set_date?: string
}): Promise<CardMeta> {
  const res = await fetch(`${BASE_URL}/cards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return data.card as CardMeta
}

export async function deleteCard(cardNameEn: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/cards/${encodeURIComponent(cardNameEn)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}
