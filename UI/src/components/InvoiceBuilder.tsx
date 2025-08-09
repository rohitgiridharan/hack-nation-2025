import { useMemo, useState } from 'react'
import { useForm, useFieldArray, Controller } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
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
  fees: z.array(feeSchema).optional().default([]),
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

export default function InvoiceBuilder() {
  const [currency] = useState('USD')
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

  const totals = useMemo(() => {
    const values = watch()
    const itemsSubtotal = values.items?.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0) ?? 0
    const feesTotal = values.fees?.reduce((sum, f) => sum + f.amount, 0) ?? 0
    const grandTotal = itemsSubtotal + feesTotal
    return { itemsSubtotal, feesTotal, grandTotal }
  }, [watch])

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
            <button type="button" className="rounded-md border px-3 py-1.5 text-sm" onClick={() => itemsFieldArray.append({ sku: '', description: '', quantity: 1, unitPrice: 0, currency: 'USD' })}>Add item</button>
          </div>
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

