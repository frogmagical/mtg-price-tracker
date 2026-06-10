import { createContext, useContext } from 'react'
import type { CardMeta, ScryfallSet } from '../api'

export type CardStore = {
  cards: CardMeta[]
  setInfoMap: Record<string, ScryfallSet | null>
  loading: boolean
}

export const CardStoreContext = createContext<CardStore>({
  cards: [],
  setInfoMap: {},
  loading: true,
})

export const useCardStore = () => useContext(CardStoreContext)

const CARDS_KEY = 'mtg_cards_cache'
const SET_INFO_KEY = 'mtg_set_info_cache'
const CARDS_TTL_MS = 10 * 60 * 1000       // 10分
const SET_INFO_TTL_MS = 24 * 60 * 60 * 1000 // 24時間

type CacheEntry<T> = { data: T; expiresAt: number }

export function readCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const entry: CacheEntry<T> = JSON.parse(raw)
    if (Date.now() > entry.expiresAt) return null
    return entry.data
  } catch {
    return null
  }
}

export function writeCache<T>(key: string, data: T, ttlMs: number): void {
  try {
    const entry: CacheEntry<T> = { data, expiresAt: Date.now() + ttlMs }
    localStorage.setItem(key, JSON.stringify(entry))
  } catch {
    // localStorage quota超過等は無視
  }
}

export { CARDS_KEY, SET_INFO_KEY, CARDS_TTL_MS, SET_INFO_TTL_MS }
