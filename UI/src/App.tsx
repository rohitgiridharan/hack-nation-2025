import { useState } from 'react'
import InvoiceBuilder from './components/InvoiceBuilder'
import ShippingEstimator from './components/ShippingEstimator'
import PricingRecommendations from './components/PricingRecommendations'
import DataImport from './components/DataImport'

type TabKey = 'invoice' | 'shipping' | 'pricing' | 'import';

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('invoice');

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="text-xl font-semibold tracking-tight">Smart Pricing AI</div>
            <nav className="flex gap-2">
              <button
                className={`px-3 py-1.5 text-sm rounded-md border ${activeTab==='invoice' ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white text-neutral-800 hover:bg-neutral-50'}`}
                onClick={() => setActiveTab('invoice')}
              >
                Invoice Builder
              </button>
              <button
                className={`px-3 py-1.5 text-sm rounded-md border ${activeTab==='shipping' ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white text-neutral-800 hover:bg-neutral-50'}`}
                onClick={() => setActiveTab('shipping')}
              >
                Shipping Estimator
              </button>
              <button
                className={`px-3 py-1.5 text-sm rounded-md border ${activeTab==='pricing' ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white text-neutral-800 hover:bg-neutral-50'}`}
                onClick={() => setActiveTab('pricing')}
              >
                Price Recommendations
              </button>
              <button
                className={`px-3 py-1.5 text-sm rounded-md border ${activeTab==='import' ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white text-neutral-800 hover:bg-neutral-50'}`}
                onClick={() => setActiveTab('import')}
              >
                Data Import
              </button>
            </nav>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8">
        {activeTab === 'invoice' && (
          <div className="rounded-lg border bg-white p-4">
            <h2 className="text-lg font-semibold">Invoice Builder</h2>
            <p className="text-sm text-neutral-600">Create invoices with dynamic fees, tariffs, and promotions, then export to PDF.</p>
            <InvoiceBuilder />
          </div>
        )}

        {activeTab === 'shipping' && (
          <div className="rounded-lg border bg-white p-4">
            <h2 className="text-lg font-semibold">Shipping Estimator</h2>
            <p className="text-sm text-neutral-600">Estimate basket-level shipping from weight, dimensions, and routes.</p>
            <ShippingEstimator />
          </div>
        )}

        {activeTab === 'pricing' && (
          <div className="rounded-lg border bg-white p-4">
            <h2 className="text-lg font-semibold">Price Recommendations</h2>
            <p className="text-sm text-neutral-600">View optimal price points by product or segment from the pricing service.</p>
            <PricingRecommendations />
          </div>
        )}

        {activeTab === 'import' && (
          <div className="rounded-lg border bg-white p-4">
            <h2 className="text-lg font-semibold">Data Import</h2>
            <p className="text-sm text-neutral-600">Upload historical sales CSV to feed the pricing model.</p>
            <DataImport />
          </div>
        )}
      </main>
    </div>
  )
}

export default App
