import { useMemo } from 'react'
import { useForm } from 'react-hook-form'

type EstimatorForm = {
  originCountry: string
  destinationCountry: string
  totalWeightKg: number
  numBoxes: number
  serviceLevel: 'ground' | 'express' | 'priority'
}

const baseRatesPerKg: Record<EstimatorForm['serviceLevel'], number> = {
  ground: 4.5,
  express: 7.5,
  priority: 11.5,
}

const zoneMultiplierByPair: Record<string, number> = {
  'US->US': 1,
  'US->CA': 1.2,
  'US->EU': 1.6,
  'US->CN': 1.8,
  'EU->EU': 1,
  'EU->US': 1.5,
}

function getZoneMultiplier(origin: string, dest: string) {
  const key = `${origin}->${dest}`
  return zoneMultiplierByPair[key] ?? 1.7
}

export default function ShippingEstimator() {
  const { register, watch } = useForm<EstimatorForm>({
    defaultValues: {
      originCountry: 'US',
      destinationCountry: 'US',
      totalWeightKg: 2,
      numBoxes: 1,
      serviceLevel: 'ground',
    },
    mode: 'onChange',
  })

  const values = watch()
  const estimate = useMemo(() => {
    const weight = Math.max(0, Number(values.totalWeightKg) || 0)
    const rate = baseRatesPerKg[values.serviceLevel]
    const zone = getZoneMultiplier(values.originCountry, values.destinationCountry)
    const boxes = Math.max(1, Number(values.numBoxes) || 1)
    // Simple deterministic estimate
    const shipping = weight * rate * zone + boxes * 2.5
    const fuelSurcharge = 0.12 * shipping
    const total = shipping + fuelSurcharge
    return { shipping, fuelSurcharge, total }
  }, [values])

  return (
    <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-3">
      <section className="lg:col-span-2 rounded-lg border bg-white p-4">
        <h3 className="font-medium">Inputs</h3>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="text-sm font-medium">Origin Country</label>
            <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('originCountry')} />
          </div>
          <div>
            <label className="text-sm font-medium">Destination Country</label>
            <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('destinationCountry')} />
          </div>
          <div>
            <label className="text-sm font-medium">Total Weight (kg)</label>
            <input type="number" step="0.01" className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('totalWeightKg', { valueAsNumber: true })} />
          </div>
          <div>
            <label className="text-sm font-medium">Boxes</label>
            <input type="number" step="1" className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('numBoxes', { valueAsNumber: true })} />
          </div>
          <div className="sm:col-span-2">
            <label className="text-sm font-medium">Service Level</label>
            <select className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('serviceLevel')}>
              <option value="ground">Ground</option>
              <option value="express">Express</option>
              <option value="priority">Priority</option>
            </select>
          </div>
        </div>
      </section>

      <aside className="rounded-lg border bg-white p-4">
        <h3 className="font-medium">Estimate</h3>
        <dl className="mt-3 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-neutral-600">Base + Zone + Boxes</dt>
            <dd className="font-medium">${estimate.shipping.toFixed(2)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-neutral-600">Fuel surcharge (12%)</dt>
            <dd className="font-medium">${estimate.fuelSurcharge.toFixed(2)}</dd>
          </div>
          <div className="flex justify-between border-t pt-2">
            <dt className="text-neutral-800">Total</dt>
            <dd className="font-semibold">${estimate.total.toFixed(2)}</dd>
          </div>
        </dl>
      </aside>
    </div>
  )
}

