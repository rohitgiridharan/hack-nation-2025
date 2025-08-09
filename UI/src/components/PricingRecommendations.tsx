import { useQuery } from '@tanstack/react-query'
import React, { useState } from 'react'

type Recommendation = {
  sku: string
  currentPrice: number
  recommendedPrice: number
  liftPct: number
}

type CompetitorOffer = {
  source: string
  title: string
  url: string
  price?: number | null
  currency?: string | null
  price_text?: string | null
  matched?: boolean | null
  last_checked: string
}

type CompetitorResponse = {
  query: string
  offers: CompetitorOffer[]
  provider?: string | null
  message?: string | null
  attemptedProviders?: string[] | null
}

async function fetchRecommendations(): Promise<Recommendation[]> {
  const resp = await fetch('/api/pricing/recommendations')
  if (!resp.ok) throw new Error(`Failed to fetch recommendations (${resp.status})`)
  return resp.json()
}

async function fetchCompetitors(query: string): Promise<CompetitorResponse> {
  const url = `/api/pricing/competitors?q=${encodeURIComponent(query)}&max_results=6`
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`Failed to fetch competitors (${resp.status})`)
  const data: CompetitorResponse = await resp.json()
  return data
}

export default function PricingRecommendations() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['recommendations'],
    queryFn: fetchRecommendations,
  })
  const [expandedSku, setExpandedSku] = useState<string | null>(null)
  const [offersCache, setOffersCache] = useState<Record<string, CompetitorResponse>>({})
  const [loadingOffers, setLoadingOffers] = useState<string | null>(null)
  const [newSku, setNewSku] = useState('')
  const [newCurrent, setNewCurrent] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const onToggleOffers = async (sku: string) => {
    if (expandedSku === sku) {
      setExpandedSku(null)
      return
    }
    setExpandedSku(sku)
    if (!offersCache[sku]) {
      try {
        setLoadingOffers(sku)
        const result = await fetchCompetitors(sku)
        setOffersCache(prev => ({ ...prev, [sku]: result }))
      } finally {
        setLoadingOffers(null)
      }
    }
  }

  const onAddProduct = async (e: React.FormEvent) => {
    e.preventDefault()
    setAddError(null)
    const sku = newSku.trim()
    const current = parseFloat(newCurrent)
    if (!sku || isNaN(current)) {
      setAddError('Enter SKU and a valid current price')
      return
    }
    try {
      setAdding(true)
      const resp = await fetch('/api/pricing/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sku, currentPrice: current })
      })
      if (!resp.ok) throw new Error(`Add failed (${resp.status})`)
      // Refresh recommendations
      setNewSku('')
      setNewCurrent('')
      // Invalidate query by refetching
      // Simple approach: window reload or manual fetch then local update
      // We'll just refetch via location reload for simplicity
      // but better would be to use queryClient.invalidateQueries
      window.location.reload()
    } catch (err: any) {
      setAddError(err?.message || 'Failed to add')
    } finally {
      setAdding(false)
    }
  }

  if (isLoading) return <div className="mt-4 text-sm text-neutral-500">Loading…</div>

  return (
    <div className="mt-4 overflow-hidden rounded-lg border bg-white">
      <div className="p-3 border-b bg-neutral-50">
        <form className="flex flex-wrap items-end gap-2" onSubmit={onAddProduct}>
          <div>
            <label className="block text-xs text-neutral-600">SKU</label>
            <input value={newSku} onChange={e => setNewSku(e.target.value)} className="rounded-md border px-2 py-1 text-sm" placeholder="e.g., AB-HEPES-1KG" />
          </div>
          <div>
            <label className="block text-xs text-neutral-600">Current Price</label>
            <input value={newCurrent} onChange={e => setNewCurrent(e.target.value)} className="rounded-md border px-2 py-1 text-sm" placeholder="e.g., 199" />
          </div>
          <button type="submit" disabled={adding} className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60">{adding ? 'Adding…' : 'Add Product'}</button>
          {addError && <div className="text-xs text-red-600">{addError}</div>}
        </form>
      </div>
      <table className="min-w-full divide-y divide-neutral-200 text-sm">
        <thead className="bg-neutral-50">
          <tr>
            <th className="px-4 py-2 text-left font-medium">SKU</th>
            <th className="px-4 py-2 text-right font-medium">Current</th>
            <th className="px-4 py-2 text-right font-medium">Recommended</th>
            <th className="px-4 py-2 text-right font-medium">Lift %</th>
            <th className="px-4 py-2 text-right font-medium">Competitors</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {data.map(row => (
            <React.Fragment key={row.sku}>
              <tr>
                <td className="px-4 py-2">{row.sku}</td>
                <td className="px-4 py-2 text-right">${row.currentPrice.toFixed(2)}</td>
                <td className="px-4 py-2 text-right">${row.recommendedPrice.toFixed(2)}</td>
                <td className={`px-4 py-2 text-right ${row.liftPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>{row.liftPct.toFixed(1)}%</td>
                <td className="px-4 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => onToggleOffers(row.sku)}
                    className="rounded-md border px-2 py-1 text-xs"
                  >
                    {expandedSku === row.sku ? 'Hide' : 'Show'}
                  </button>
                </td>
              </tr>
              {expandedSku === row.sku && (
                <tr key={`${row.sku}-expanded`}>
                  <td colSpan={5} className="px-4 py-2 bg-neutral-50">
                    {loadingOffers === row.sku && (
                      <div className="text-xs text-neutral-600">Loading competitor offers…</div>
                    )}
                    {!loadingOffers && (
                      <div className="space-y-2">
                        {(!offersCache[row.sku] || (offersCache[row.sku]?.offers?.length ?? 0) === 0) ? (
                          <div className="text-xs text-neutral-700">
                            <div className="font-medium">No offers found.</div>
                            {offersCache[row.sku]?.message && (
                              <div className="mt-1 text-neutral-600">{offersCache[row.sku]?.message}</div>
                            )}
                            <div className="mt-1 text-neutral-600">
                              Tips: try a more specific query (include brand, pack size), check your network, or try again later.
                              {offersCache[row.sku]?.provider && (
                                <span> Provider: {offersCache[row.sku]?.provider}</span>
                              )}
                              {offersCache[row.sku]?.attemptedProviders?.length ? (
                                <span> (Tried: {(offersCache[row.sku]?.attemptedProviders || []).join(', ')})</span>
                              ) : null}
                            </div>
                          </div>
                        ) : (
                          <ul className="space-y-1">
                            {(offersCache[row.sku]?.offers || []).map((o, i) => (
                              <li key={i} className="flex items-center justify-between gap-2">
                                <div className="min-w-0">
                                  <a href={o.url} target="_blank" rel="noreferrer" className="text-xs font-medium text-blue-700 hover:underline truncate block">
                                    {o.title || o.source}
                                  </a>
                                  <div className="text-[11px] text-neutral-600 truncate">{o.source}</div>
                                </div>
                                <div className="text-xs text-right min-w-[100px]">
                                  {o.price != null ? (
                                    <span className="font-semibold">{o.currency || '$'} {o.price.toFixed(2)}</span>
                                  ) : (
                                    <span className="text-neutral-500">n/a</span>
                                  )}
                                  {o.matched != null && (
                                    <div className={`text-[10px] ${o.matched ? 'text-green-700' : 'text-neutral-500'}`}>{o.matched ? 'Match' : 'Unclear'}</div>
                                  )}
                                </div>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

