import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation } from '@tanstack/react-query'

type EstimatorForm = {
  originZipCode: string
  destinationZipCode: string
  totalWeightKg: number
  numBoxes: number
  serviceLevel: 'ground' | 'express' | 'priority'
}

type ShippingEstimate = {
  origin_zip: string
  destination_zip: string
  weight_kg: number
  num_boxes: number
  service_level: string
  estimated_cost: number
  breakdown: {
    base_shipping: number
    fuel_surcharge: number
    handling_fee: number
  }
  provider: string
  message: string
}

async function fetchShippingEstimate(data: EstimatorForm): Promise<ShippingEstimate> {
  const response = await fetch('/api/shipping/estimate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      origin_zip: data.originZipCode,
      destination_zip: data.destinationZipCode,
      weight_kg: data.totalWeightKg,
      num_boxes: data.numBoxes,
      service_level: data.serviceLevel,
    }),
  })
  
  if (!response.ok) {
    throw new Error(`Shipping estimation failed: ${response.statusText}`)
  }
  
  return response.json()
}

export default function ShippingEstimator() {
  const { register, watch, handleSubmit } = useForm<EstimatorForm>({
    defaultValues: {
      originZipCode: '10001',
      destinationZipCode: '90210',
      totalWeightKg: 2,
      numBoxes: 1,
      serviceLevel: 'ground',
    },
    mode: 'onChange',
  })

  const [estimate, setEstimate] = useState<ShippingEstimate | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const shippingMutation = useMutation({
    mutationFn: fetchShippingEstimate,
    onSuccess: (data) => {
      setEstimate(data)
      setIsLoading(false)
    },
    onError: (error) => {
      console.error('Shipping estimation error:', error)
      setIsLoading(false)
    },
  })

  const onSubmit = (data: EstimatorForm) => {
    setIsLoading(true)
    shippingMutation.mutate(data)
  }

  const values = watch()

  return (
    <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-3">
      <section className="lg:col-span-2 rounded-lg border bg-white p-4">
        <h3 className="font-medium">Inputs</h3>
        <form onSubmit={handleSubmit(onSubmit)} className="mt-4 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Origin Zip Code</label>
              <input 
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm" 
                placeholder="e.g., 10001"
                maxLength={10}
                {...register('originZipCode')} 
              />
            </div>
            <div>
              <label className="text-sm font-medium">Destination Zip Code</label>
              <input 
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm" 
                placeholder="e.g., 90210"
                maxLength={10}
                {...register('destinationZipCode')} 
              />
            </div>
            <div>
              <label className="text-sm font-medium">Total Weight (kg)</label>
              <input 
                type="number" 
                step="0.01" 
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm" 
                {...register('totalWeightKg', { valueAsNumber: true })} 
              />
            </div>
            <div>
              <label className="text-sm font-medium">Boxes</label>
              <input 
                type="number" 
                step="1" 
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm" 
                {...register('numBoxes', { valueAsNumber: true })} 
              />
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
          
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isLoading}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Calculating...' : 'Get Shipping Estimate'}
            </button>
          </div>
        </form>
      </section>

      <aside className="rounded-lg border bg-white p-4">
        <h3 className="font-medium">Estimate</h3>
        {isLoading ? (
          <div className="mt-3 text-sm text-gray-500">
            Calculating shipping costs...
          </div>
        ) : estimate ? (
          <div className="mt-3 space-y-3">
            <div className="text-xs text-gray-500">
              Provider: {estimate.provider}
            </div>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-neutral-600">Base Shipping</dt>
                <dd className="font-medium">${estimate.breakdown.base_shipping.toFixed(2)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-neutral-600">Fuel Surcharge</dt>
                <dd className="font-medium">${estimate.breakdown.fuel_surcharge.toFixed(2)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-neutral-600">Handling Fee</dt>
                <dd className="font-medium">${estimate.breakdown.handling_fee.toFixed(2)}</dd>
              </div>
              <div className="flex justify-between border-t pt-2">
                <dt className="text-neutral-800">Total</dt>
                <dd className="font-semibold">${estimate.estimated_cost.toFixed(2)}</dd>
              </div>
            </dl>
            {estimate.message && (
              <div className="mt-3 text-xs text-gray-600 border-t pt-2">
                {estimate.message}
              </div>
            )}
          </div>
        ) : (
          <div className="mt-3 text-sm text-gray-500">
            Enter package details and click "Get Shipping Estimate" to calculate costs using AI.
          </div>
        )}
      </aside>
    </div>
  )
}

