import { useMemo, useRef, useState } from 'react'
import Papa from 'papaparse'

const REQUIRED_HEADERS = [
  'order_id','date_ordered','product_type','customer_type','price','competitor_price','promotion_flag','marketing_spend','economic_index','seasonality_index','trend_index','day_of_week','month','price_gap','quantity'
] as const

type Row = Record<(typeof REQUIRED_HEADERS)[number], string>

type ParseResult = {
  rows: Row[]
  missingHeaders: string[]
  extraHeaders: string[]
}

function validateHeaders(headers: string[]): { missing: string[]; extra: string[] } {
  const normalized = headers.map(h => h.trim())
  const missing = REQUIRED_HEADERS.filter(h => !normalized.includes(h))
  const extra = normalized.filter(h => !REQUIRED_HEADERS.includes(h as any))
  return { missing, extra }
}

export default function DataImport() {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const [parseResult, setParseResult] = useState<ParseResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadSucceeded, setUploadSucceeded] = useState(false)
  const [isRetraining, setIsRetraining] = useState(false)
  const [retrainMessage, setRetrainMessage] = useState<string | null>(null)

  const handleFile = (file: File) => {
    setError(null)
    setFileName(file.name)
    Papa.parse<Row>(file, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: false,
      complete: (res) => {
        const headers = res.meta.fields ?? []
        const { missing, extra } = validateHeaders(headers)

        if (missing.length > 0) {
          setParseResult({ rows: [], missingHeaders: missing, extraHeaders: extra })
          return
        }

        // Coerce row keys to required set
        const rows: Row[] = (res.data as any[]).map((r) => {
          const row: Partial<Row> = {}
          REQUIRED_HEADERS.forEach((key) => {
            row[key] = (r?.[key] ?? '').toString()
          })
          return row as Row
        })

        setParseResult({ rows, missingHeaders: missing, extraHeaders: extra })
      },
      error: (err) => {
        setError(err.message)
      }
    })
  }

  const onSelectFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
  }

  const previewRows = useMemo(() => parseResult?.rows.slice(0, 10) ?? [], [parseResult])

  const onSubmitToBackend = async () => {
    if (!parseResult || parseResult.rows.length === 0) return
    try {
      setIsSubmitting(true)
      setUploadSucceeded(false)
      // Replace with your actual endpoint when the pricing service is ready
      const endpoint = import.meta.env.VITE_PRICING_UPLOAD_URL || '/api/pricing/upload'
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: parseResult.rows })
      })
      if (!resp.ok) throw new Error(`Upload failed (${resp.status})`)
      setUploadSucceeded(true)
      alert('Data uploaded successfully.')
    } catch (e: any) {
      setError(e?.message || 'Upload failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  const onRetrain = async () => {
    try {
      setIsRetraining(true)
      setRetrainMessage(null)
      const endpoint = import.meta.env.VITE_PRICING_RETRAIN_URL || '/api/pricing/retrain'
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: 'ui-upload',
          fileName,
          numRows: parseResult?.rows.length ?? 0,
          schema: REQUIRED_HEADERS,
        }),
      })
      if (!resp.ok) throw new Error(`Retrain failed (${resp.status})`)
      const payload = await resp.json().catch(() => ({}))
      setRetrainMessage(payload?.message || 'Retraining started. This may take several minutes.')
    } catch (e: any) {
      setError(e?.message || 'Retrain failed')
    } finally {
      setIsRetraining(false)
    }
  }

  return (
    <div className="mt-4 space-y-6">
      <div
        className="rounded-lg border border-dashed bg-white p-6 text-center hover:bg-neutral-50"
        onDrop={onDrop}
        onDragOver={onDragOver}
      >
        <p className="text-sm text-neutral-700">Drag and drop your CSV here, or</p>
        <button
          type="button"
          className="mt-2 rounded-md border px-3 py-1.5 text-sm"
          onClick={() => inputRef.current?.click()}
        >
          Browse files
        </button>
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={onSelectFile} />
        {fileName && <p className="mt-2 text-xs text-neutral-500">Selected: {fileName}</p>}
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {parseResult && (
        <div className="space-y-4">
          {(parseResult.missingHeaders.length > 0 || parseResult.extraHeaders.length > 0) && (
            <div className="rounded-md border bg-white p-4 text-sm">
              {parseResult.missingHeaders.length > 0 && (
                <p className="text-red-700">Missing headers: {parseResult.missingHeaders.join(', ')}</p>
              )}
              {parseResult.extraHeaders.length > 0 && (
                <p className="text-neutral-600 mt-1">Extra headers (ignored): {parseResult.extraHeaders.join(', ')}</p>
              )}
            </div>
          )}

          {parseResult.rows.length > 0 && (
            <div className="overflow-hidden rounded-lg border bg-white">
              <table className="min-w-full divide-y divide-neutral-200 text-sm">
                <thead className="bg-neutral-50">
                  <tr>
                    {REQUIRED_HEADERS.map(h => (
                      <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {previewRows.map((row, idx) => (
                    <tr key={idx}>
                      {REQUIRED_HEADERS.map(h => (
                        <td key={h} className="px-3 py-2">{row[h]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-3 py-2 text-xs text-neutral-500">Showing first {previewRows.length} of {parseResult.rows.length} rows</div>
            </div>
          )}

          <div className="flex items-center justify-end gap-2">
            <a
              href={`data:text/csv;charset=utf-8,${encodeURIComponent(REQUIRED_HEADERS.join(',') + '\n')}`}
              download="pricing-data-template.csv"
              className="rounded-md border px-3 py-1.5 text-sm"
            >
              Download template
            </a>
            <button
              type="button"
              disabled={isSubmitting || (parseResult.rows.length === 0)}
              onClick={onSubmitToBackend}
              className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
            >
              {isSubmitting ? 'Uploading…' : 'Upload to Pricing Service'}
            </button>
            {uploadSucceeded && (
              <button
                type="button"
                disabled={isRetraining}
                onClick={onRetrain}
                className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-60"
              >
                {isRetraining ? 'Starting retrain…' : 'Retrain Pricing Model'}
              </button>
            )}
          </div>
          {retrainMessage && (
            <div className="text-xs text-neutral-600">{retrainMessage}</div>
          )}
        </div>
      )}
    </div>
  )
}

