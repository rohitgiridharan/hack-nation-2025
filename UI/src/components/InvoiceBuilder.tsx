import { useMemo, useState } from 'react'
import { useForm, useFieldArray, Controller } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import dayjs from 'dayjs'

const invoiceItemSchema = z.object({
  sku: z.string().min(1),
  description: z.string().min(1),
  quantity: z.coerce.number().min(1),
  unitPrice: z.coerce.number().min(0),
  currency: z.string().default('USD'),
  weightKg: z.coerce.number().optional(),
  hsCode: z.string().optional(),
  originCountry: z.string().optional(),
})

const feeSchema = z.object({
  type: z.enum(['tariff', 'service', 'handling', 'promotion', 'other']),
  label: z.string().min(1),
  amount: z.coerce.number(),
})

const formSchema = z.object({
  invoiceNumber: z.string().min(1),
  invoiceDate: z.string().min(1),
  supplier: z.object({
    name: z.string().min(1),
    address: z.string().min(1),
    country: z.string().min(1),
  }),
  buyer: z.object({
    name: z.string().min(1),
    segment: z.enum(['academic', 'biotech', 'pharma', 'distributor', 'other']),
    address: z.string().min(1),
    country: z.string().min(1),
  }),
  items: z.array(invoiceItemSchema).min(1),
  fees: z.array(feeSchema),
  notes: z.string().optional(),
})

export type InvoiceFormValues = z.infer<typeof formSchema>

const defaultValues: InvoiceFormValues = {
  invoiceNumber: 'INV-1001',
  invoiceDate: dayjs().format('YYYY-MM-DD'),
  supplier: {
    name: 'Acme Life Sciences',
    address: '123 Science Park Blvd\nBoston, MA 02115',
    country: 'US',
  },
  buyer: {
    name: 'Atlas Biotech Inc.',
    segment: 'biotech',
    address: '500 Mission St\nSan Francisco, CA 94105',
    country: 'US',
  },
  items: [
    {
      sku: 'AB-HEPES-1KG',
      description: 'HEPES Buffer 1kg, molecular biology grade',
      quantity: 2,
      unitPrice: 185.0,
      currency: 'USD',
      weightKg: 1.0,
      hsCode: '2933.99',
      originCountry: 'US',
    },
  ],
  fees: [
    { type: 'service', label: 'Cold chain packaging', amount: 25 },
    { type: 'handling', label: 'Hazmat handling', amount: 15 },
  ],
  notes: 'Thank you for your business.',
}

function formatCurrency(value: number, currency = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value)
}

type PricingRecommendation = {
  sku: string
  current_price: number
  recommended_price: number
  pricing_strategy: string
  reasoning: string
  market_factors: string[]
  confidence_level: string
}

type InvoicePricingResponse = {
  recommendations: PricingRecommendation[]
  provider: string
  message: string
}

export default function InvoiceBuilder() {
  const [currency] = useState('USD')
  const [pricingResults, setPricingResults] = useState<InvoicePricingResponse | null>(null)
  const [debugInfo, setDebugInfo] = useState<{
    requestData: any
    responseData: any
    timestamp: string
  } | null>(null)

  const {
    control,
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<InvoiceFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
    mode: 'onChange',
  })

  const itemsFieldArray = useFieldArray({ control, name: 'items' })
  const feesFieldArray = useFieldArray({ control, name: 'fees' })

  // Pricing mutation
  const pricingMutation = useMutation({
    mutationFn: async (data: InvoiceFormValues) => {
      console.log('Pricing mutation triggered with data:', data)
      
      // Validate that we have the required data
      if (!data.items || data.items.length === 0) {
        throw new Error('No items found in invoice')
      }
      
      if (!data.buyer.segment || !data.buyer.country || !data.supplier.country) {
        throw new Error('Missing buyer or supplier information')
      }
      
      const requestData = {
        items: data.items.map(item => ({
          sku: item.sku,
          description: item.description,
          quantity: item.quantity,
          unitPrice: item.unitPrice
        })),
        buyer_segment: data.buyer.segment,
        buyer_country: data.buyer.country,
        supplier_country: data.supplier.country,
      }
      
      console.log('Sending pricing request:', requestData)
      
      // Store request data for debugging
      setDebugInfo({
        requestData: requestData,
        responseData: null,
        timestamp: new Date().toISOString()
      })
      
      const response = await fetch('/api/pricing/invoice', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      })
      
      console.log('Pricing response status:', response.status)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Pricing API error:', errorText)
        
        // Update debug info with error response
        setDebugInfo(prev => prev ? {
          ...prev,
          responseData: { error: errorText, status: response.status }
        } : null)
        
        throw new Error(`Pricing generation failed: ${response.status} ${response.statusText}`)
      }
      
      const result = await response.json()
      console.log('Pricing API success:', result)
      
      // Update debug info with successful response
      setDebugInfo(prev => prev ? {
        ...prev,
        responseData: result
      } : null)
      
      return result as InvoicePricingResponse
    },
    onSuccess: (data) => {
      console.log('Pricing mutation success:', data)
      setPricingResults(data)
    },
    onError: (error) => {
      console.error('Pricing mutation error:', error)
      alert(`Pricing generation failed: ${error.message}`)
    },
  })

  const onGeneratePdf = (values: InvoiceFormValues) => {
    const doc = new jsPDF({ unit: 'pt', format: 'a4' })

    const marginX = 40
    let cursorY = 40

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(16)
    doc.text('Invoice', marginX, cursorY)
    cursorY += 12

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(10)
    doc.text(`Invoice #: ${values.invoiceNumber}`, marginX, cursorY)
    cursorY += 14
    doc.text(`Date: ${dayjs(values.invoiceDate).format('MMM D, YYYY')}`, marginX, cursorY)

    // Parties
    cursorY += 24
    doc.setFont('helvetica', 'bold')
    doc.text('Supplier', marginX, cursorY)
    doc.text('Buyer', 320, cursorY)
    doc.setFont('helvetica', 'normal')
    cursorY += 14
    doc.text([values.supplier.name, values.supplier.address, values.supplier.country], marginX, cursorY)
    doc.text([values.buyer.name, values.buyer.address, `${values.buyer.country} (${values.buyer.segment})`], 320, cursorY)

    // Items table
    autoTable(doc, {
      startY: cursorY + 60,
      head: [[
        'SKU', 'Description', 'Qty', 'Unit Price', 'Line Total',
      ]],
      body: values.items.map(item => [
        item.sku,
        item.description,
        String(item.quantity),
        formatCurrency(item.unitPrice, item.currency),
        formatCurrency(item.unitPrice * item.quantity, item.currency),
      ]),
      styles: { fontSize: 9 },
      headStyles: { fillColor: [20, 20, 20] },
      columnStyles: { 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'right' } },
    })

    let afterTableY = (doc as any).lastAutoTable.finalY || cursorY + 60

    // Fees table (if any)
    if ((values.fees?.length ?? 0) > 0) {
      autoTable(doc, {
        startY: afterTableY + 16,
        head: [['Fee Type', 'Label', 'Amount']],
        body: values.fees!.map(f => [f.type, f.label, formatCurrency(f.amount, currency)]),
        styles: { fontSize: 9 },
        headStyles: { fillColor: [240, 240, 240], textColor: [20,20,20] },
        columnStyles: { 2: { halign: 'right' } },
      })
      afterTableY = (doc as any).lastAutoTable.finalY
    }

    // Totals
    const rightX = 555
    doc.setFont('helvetica', 'bold')
    doc.text('Subtotal:', rightX - 120, afterTableY + 24, { align: 'right' })
    doc.text('Fees:', rightX - 120, afterTableY + 40, { align: 'right' })
    doc.text('Total:', rightX - 120, afterTableY + 56, { align: 'right' })
    doc.setFont('helvetica', 'normal')
    doc.text(formatCurrency(totals.itemsSubtotal, currency), rightX, afterTableY + 24, { align: 'right' })
    doc.text(formatCurrency(totals.feesTotal, currency), rightX, afterTableY + 40, { align: 'right' })
    doc.setFont('helvetica', 'bold')
    doc.text(formatCurrency(totals.grandTotal, currency), rightX, afterTableY + 56, { align: 'right' })

    // Notes
    if (values.notes) {
      doc.setFont('helvetica', 'normal')
      autoTable(doc, {
        startY: afterTableY + 80,
        theme: 'plain',
        body: [[`Notes: ${values.notes}`]],
        styles: { fontSize: 9 },
      })
    }

    doc.save(`${values.invoiceNumber}.pdf`)
  }

  const onGeneratePricing = (data: InvoiceFormValues) => {
    console.log('Generate pricing clicked with data:', data)
    console.log('Raw form data:', JSON.stringify(data, null, 2))
    
    // Check if form is valid
    if (!data.items || data.items.length === 0) {
      alert('Please add at least one item to the invoice before generating pricing.')
      return
    }
    
    if (!data.buyer.segment || !data.buyer.country || !data.supplier.country) {
      alert('Please fill in all buyer and supplier information before generating pricing.')
      return
    }
    
    // Log the specific fields being sent
    console.log('Items being sent:', data.items)
    console.log('Buyer segment:', data.buyer.segment)
    console.log('Buyer country:', data.buyer.country)
    console.log('Supplier country:', data.supplier.country)
    
    // Check for any undefined or null values
    const hasUndefinedValues = data.items.some(item => 
      item.sku === undefined || 
      item.description === undefined || 
      item.quantity === undefined || 
      item.unitPrice === undefined
    )
    
    if (hasUndefinedValues) {
      console.error('Found undefined values in items:', data.items)
      alert('Some item fields are undefined. Please check your form data.')
      return
    }
    
    console.log('Starting pricing generation...')
    pricingMutation.mutate(data)
  }

  const totals = useMemo(() => {
    const values = watch()
    const itemsSubtotal = values.items?.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0) ?? 0
    const feesTotal = values.fees?.reduce((sum, f) => sum + f.amount, 0) ?? 0
    const grandTotal = itemsSubtotal + feesTotal
    return { itemsSubtotal, feesTotal, grandTotal }
  }, [watch])

  return (
    <form className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-3" onSubmit={handleSubmit(onGeneratePdf)}>
      <section className="lg:col-span-2 space-y-6">
        <div className="rounded-lg border bg-white p-4">
          <h3 className="font-medium">Header</h3>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Invoice #</label>
              <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('invoiceNumber')} />
              {errors.invoiceNumber && <p className="text-xs text-red-600">Required</p>}
            </div>
            <div>
              <label className="text-sm font-medium">Date</label>
              <input type="date" className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('invoiceDate')} />
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-white p-4">
          <h3 className="font-medium">Parties</h3>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Supplier Name</label>
              <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('supplier.name')} />
              <label className="mt-3 block text-sm font-medium">Supplier Address</label>
              <textarea className="mt-1 w-full rounded-md border px-3 py-2 text-sm" rows={3} {...register('supplier.address')} />
              <label className="mt-3 block text-sm font-medium">Supplier Country</label>
              <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('supplier.country')} />
            </div>
            <div>
              <label className="text-sm font-medium">Buyer Name</label>
              <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('buyer.name')} />
              <label className="mt-3 block text-sm font-medium">Buyer Segment</label>
              <select className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('buyer.segment')}>
                <option value="academic">Academic</option>
                <option value="biotech">Biotech startup</option>
                <option value="pharma">Pharma enterprise</option>
                <option value="distributor">Distributor</option>
                <option value="other">Other</option>
              </select>
              <label className="mt-3 block text-sm font-medium">Buyer Address</label>
              <textarea className="mt-1 w-full rounded-md border px-3 py-2 text-sm" rows={3} {...register('buyer.address')} />
              <label className="mt-3 block text-sm font-medium">Buyer Country</label>
              <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" {...register('buyer.country')} />
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Line Items</h3>
            <div className="flex gap-2">
              <button 
                type="button" 
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
                onClick={() => {
                  console.log('Button clicked!')
                  onGeneratePricing(watch())
                }}
                disabled={pricingMutation.isPending}
              >
                {pricingMutation.isPending ? 'Generating...' : 'Generate Pricing'}
              </button>
              <button 
                type="button" 
                className="rounded-md border px-3 py-1.5 text-sm" 
                onClick={() => itemsFieldArray.append({ sku: '', description: '', quantity: 1, unitPrice: 0, currency: 'USD' })}
              >
                Add item
              </button>
            </div>
          </div>
          
          {/* Pricing Results */}
          {pricingResults && (
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
              <h3 className="text-lg font-semibold text-blue-800 mb-2">AI Pricing Recommendations</h3>
              <div className="space-y-2">
                {pricingResults.recommendations.map((rec, index) => (
                  <div key={index} className="p-3 bg-white border border-blue-200 rounded">
                    <div className="font-medium text-blue-700">SKU: {rec.sku}</div>
                    <div className="text-sm text-gray-600">
                      Current Price: ${rec.current_price}
                    </div>
                    <div className="text-sm text-gray-600">
                      Recommended Price: ${rec.recommended_price}
                    </div>
                    <div className="text-sm text-gray-600">
                      Strategy: {rec.pricing_strategy}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-2 text-sm text-blue-600">
                Provider: {pricingResults.provider} | {pricingResults.message}
              </div>
            </div>
          )}

          {/* Debug Information */}
          {debugInfo && (
            <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-md">
              <h3 className="text-lg font-semibold text-gray-800 mb-2">🔍 Debug Information</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">📤 Request Sent to Backend</h4>
                  <pre className="text-xs bg-white p-2 border rounded overflow-auto max-h-40">
                    {JSON.stringify(debugInfo.requestData, null, 2)}
                  </pre>
                  <div className="text-xs text-gray-500 mt-1">
                    Timestamp: {new Date(debugInfo.timestamp).toLocaleString()}
                  </div>
                </div>
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">📥 Response from Backend</h4>
                  <pre className="text-xs bg-white p-2 border rounded overflow-auto max-h-40">
                    {debugInfo.responseData ? JSON.stringify(debugInfo.responseData, null, 2) : 'Waiting for response...'}
                  </pre>
                </div>
              </div>
            </div>
          )}
          
          <div className="mt-4 space-y-4">
            {itemsFieldArray.fields.map((field, index) => (
              <div key={field.id} className="grid grid-cols-1 gap-3 sm:grid-cols-6">
                <input placeholder="SKU" className="rounded-md border px-3 py-2 text-sm sm:col-span-1" {...register(`items.${index}.sku` as const)} />
                <input placeholder="Description" className="rounded-md border px-3 py-2 text-sm sm:col-span-2" {...register(`items.${index}.description` as const)} />
                <input type="number" step="1" placeholder="Qty" className="rounded-md border px-3 py-2 text-sm sm:col-span-1" {...register(`items.${index}.quantity` as const)} />
                <input type="number" step="0.01" placeholder="Unit Price" className="rounded-md border px-3 py-2 text-sm sm:col-span-1" {...register(`items.${index}.unitPrice` as const)} />
                <input placeholder="Currency" className="rounded-md border px-3 py-2 text-sm sm:col-span-1" {...register(`items.${index}.currency` as const)} />
                <button type="button" className="sm:col-span-6 justify-self-end text-sm text-red-600" onClick={() => itemsFieldArray.remove(index)}>Remove</button>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Fees, Tariffs, Promotions</h3>
            <button type="button" className="rounded-md border px-3 py-1.5 text-sm" onClick={() => feesFieldArray.append({ type: 'service', label: '', amount: 0 })}>Add fee</button>
          </div>
          <div className="mt-4 space-y-4">
            {feesFieldArray.fields.map((field, index) => (
              <div key={field.id} className="grid grid-cols-1 gap-3 sm:grid-cols-6">
                <select className="rounded-md border px-3 py-2 text-sm sm:col-span-2" {...register(`fees.${index}.type` as const)}>
                  <option value="tariff">Tariff</option>
                  <option value="service">Service</option>
                  <option value="handling">Handling</option>
                  <option value="promotion">Promotion</option>
                  <option value="other">Other</option>
                </select>
                <input placeholder="Label" className="rounded-md border px-3 py-2 text-sm sm:col-span-3" {...register(`fees.${index}.label` as const)} />
                <input type="number" step="0.01" placeholder="Amount" className="rounded-md border px-3 py-2 text-sm sm:col-span-1" {...register(`fees.${index}.amount` as const)} />
                <button type="button" className="sm:col-span-6 justify-self-end text-sm text-red-600" onClick={() => feesFieldArray.remove(index)}>Remove</button>
              </div>
            ))}
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-lg border bg-white p-4">
          <h3 className="font-medium">Summary</h3>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-neutral-600">Items subtotal</dt>
              <dd className="font-medium">{formatCurrency(totals.itemsSubtotal, currency)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-neutral-600">Fees</dt>
              <dd className="font-medium">{formatCurrency(totals.feesTotal, currency)}</dd>
            </div>
            <div className="flex justify-between border-t pt-2">
              <dt className="text-neutral-800">Total</dt>
              <dd className="font-semibold">{formatCurrency(totals.grandTotal, currency)}</dd>
            </div>
          </dl>
          <button type="submit" className="mt-4 w-full rounded-md bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800">Download PDF</button>
        </div>

        <div className="rounded-lg border bg-white p-4">
          <h3 className="font-medium">Notes</h3>
          <textarea rows={5} className="mt-2 w-full rounded-md border px-3 py-2 text-sm" placeholder="Payment terms, delivery notes, etc." {...register('notes')} />
        </div>
      </aside>
    </form>
  )
}

