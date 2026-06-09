import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchCards, type CardMeta } from '../api'

export default function CardSearchPage() {
  const [cards, setCards] = useState<CardMeta[]>([])
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    fetchCards().then(setCards).catch(console.error)
  }, [])

  const filtered = cards.filter(
    (c) =>
      c.card_name_en.toLowerCase().includes(query.toLowerCase()) ||
      c.card_name_ja.includes(query),
  )

  return (
    <div style={{ padding: 16, maxWidth: 600, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, marginBottom: 12 }}>MTG Price Tracker</h1>
      <input
        type="search"
        placeholder="カード名で検索（日本語・英語）"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{ width: '100%', padding: 8, fontSize: 16, marginBottom: 16, boxSizing: 'border-box' }}
      />
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {filtered.map((c) => (
          <li
            key={c.card_name_en}
            onClick={() => navigate(`/prices/${encodeURIComponent(c.card_name_en)}`)}
            style={{ padding: '12px 0', borderBottom: '1px solid #eee', cursor: 'pointer' }}
          >
            <span style={{ fontWeight: 'bold' }}>{c.card_name_ja || c.card_name_en}</span>
            <span style={{ color: '#888', marginLeft: 8, fontSize: 12 }}>{c.card_name_en}</span>
            <span style={{ color: '#aaa', marginLeft: 8, fontSize: 11 }}>{c.latest_set_code}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
