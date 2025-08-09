import { useQuery } from '@tanstack/react-query'

type Recommendation = {
  sku: string
  currentPrice: number
  recommendedPrice: number
  liftPct: number
}

async function fetchRecommendations(): Promise<Recommendation[]> {
  // Placeholder: fetch from your pricing service endpoint when available
  return [
    { sku: 'AB-HEPES-1KG', currentPrice: 185, recommendedPrice: 199, liftPct: 7.6 },
    { sku: 'TF-PIPET-200', currentPrice: 29, recommendedPrice: 27, liftPct: -6.9 },
  ]
}

export default function PricingRecommendations() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['recommendations'],
    queryFn: fetchRecommendations,
  })

  if (isLoading) return <div className="mt-4 text-sm text-neutral-500">Loading…</div>

  return (
    <div className="mt-4 overflow-hidden rounded-lg border bg-white">
      <table className="min-w-full divide-y divide-neutral-200 text-sm">
        <thead className="bg-neutral-50">
          <tr>
            <th className="px-4 py-2 text-left font-medium">SKU</th>
            <th className="px-4 py-2 text-right font-medium">Current</th>
            <th className="px-4 py-2 text-right font-medium">Recommended</th>
            <th className="px-4 py-2 text-right font-medium">Lift %</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {data.map(row => (
            <tr key={row.sku}>
              <td className="px-4 py-2">{row.sku}</td>
              <td className="px-4 py-2 text-right">${row.currentPrice.toFixed(2)}</td>
              <td className="px-4 py-2 text-right">${row.recommendedPrice.toFixed(2)}</td>
              <td className={`px-4 py-2 text-right ${row.liftPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>{row.liftPct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

