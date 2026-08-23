const STEPS = [
  ['Extract', 'pymupdf4llm pulls text, headings, and layout from each PDF'],
  ['Chunk', 'Groups content by section heading, not fixed-size windows'],
  ['Embed', 'fastembed (BAAI/bge-small-en-v1.5), 384 dims, runs on CPU'],
  ['Search', 'Hybrid semantic + natural-language date filtering over pgvector'],
] as const;

function App() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <header className="border-b px-6 py-4 flex items-center justify-between max-w-4xl mx-auto">
        <span className="font-bold">QueryNest</span>
        <a
          href="https://github.com/Apoorv012/QueryNest-New"
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Source
        </a>
      </header>

      <main className="max-w-4xl mx-auto px-6">
        <section className="py-20 text-center">
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            Search your PDFs by meaning, not keywords
          </h1>
          <p className="text-gray-500 text-lg max-w-2xl mx-auto mb-8">
            QueryNest is a semantic search engine for personal PDFs — ask a question in
            plain English, including dates ("deadlock bugs from last year"), and get the
            passages that actually answer it.
          </p>
          <a
            href="/demo/"
            className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            Try the live demo →
          </a>
          <p className="text-xs text-gray-400 mt-3">
            Searches a pre-loaded, read-only corpus — no sign-up, no upload needed.
          </p>
        </section>

        <section className="py-16 border-t">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-8 text-center">
            How it works
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-6">
            {STEPS.map(([title, desc], i) => (
              <div key={title} className="text-center">
                <div className="text-xs font-mono text-gray-300 mb-2">0{i + 1}</div>
                <div className="font-semibold mb-1">{title}</div>
                <div className="text-sm text-gray-500">{desc}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="py-16 border-t text-center">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
            Stack
          </h2>
          <p className="text-gray-500 text-sm max-w-xl mx-auto">
            FastAPI · pgvector on Supabase Postgres · fastembed (ONNX, CPU-only) ·
            React + Vite dashboard for ingest/search. Answer generation with citations
            and PDF highlight annotation are next.
          </p>
        </section>
      </main>

      <footer className="text-center text-xs text-gray-400 py-8 border-t">
        Built as a portfolio project.{' '}
        <a href="/demo/" className="underline hover:text-gray-600">
          Try the demo
        </a>
      </footer>
    </div>
  );
}

export default App;
