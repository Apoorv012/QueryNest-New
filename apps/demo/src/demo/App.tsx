import { useState, useEffect, useCallback } from 'react';
import { FileList } from './components/FileList';
import { SearchBar } from './components/SearchBar';
import { SearchResults } from './components/SearchResults';
import { Disabled } from './components/Disabled';
import { listDocuments, search, checkBackend } from './lib/api';
import type { DocumentInfo, SearchResponse } from './lib/api';

function App() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);

  const refreshDocs = useCallback(async () => {
    try {
      setDocuments(await listDocuments());
    } catch {
      setDocuments([]);
    }
  }, []);

  useEffect(() => {
    refreshDocs();
  }, [refreshDocs]);

  useEffect(() => {
    // /check-backend, not /health: ad-blockers (Brave Shields included)
    // filter generic paths like /health, /ping, /beacon as tracking pings,
    // silently failing the request client-side with zero bytes transferred
    // — the API was never actually reached, so it looked "down" to a
    // browser that had never sent the request. See lib/api.ts.
    //
    // A cold Render instance can also 502 the first request or two while it
    // spins up, so two consecutive failures are required before flipping to
    // "offline" — a single success always clears it immediately.
    let consecutiveFailures = 0;
    const check = async () => {
      const ok = await checkBackend();
      if (ok) {
        consecutiveFailures = 0;
        setOnline(true);
      } else {
        consecutiveFailures += 1;
        if (consecutiveFailures >= 2) setOnline(false);
      }
    };
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, []);

  const handleSearch = async (query: string, dateFrom: string | null, dateTo: string | null) => {
    setSearching(true);
    try {
      const result = await search(query, { dateFrom: dateFrom ?? undefined, dateTo: dateTo ?? undefined });
      setSearchResult(result);
      setOnline(true);
    } catch {
      setSearchResult(null);
    }
    setSearching(false);
  };

  return (
    <div className="h-screen flex flex-col bg-white">
      <header className="border-b px-4 py-2 flex items-center gap-4">
        <a href="/" className="font-bold text-sm">
          QueryNest
        </a>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">User:</label>
          <span
            title="This demo only searches the read-only golden_user corpus"
            className="border rounded px-2 py-1 text-sm w-40 bg-gray-100 text-gray-500 cursor-not-allowed"
          >
            golden_user
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="flex items-center gap-1 text-xs">
            <span className={`w-2 h-2 rounded-full ${online === null ? 'bg-gray-300' : online ? 'bg-green-500' : 'bg-red-500'}`} />
            {online === null ? 'checking...' : online ? 'online' : 'offline'}
          </span>
          <Disabled message="Read-only demo — reseeding is admin-only" direction="down">
            <button className="bg-amber-600 text-white text-xs px-3 py-1 rounded">
              Seed Golden Set
            </button>
          </Disabled>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <FileList documents={documents} />

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="p-4 border-b">
            <SearchBar onSearch={handleSearch} loading={searching} />
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <SearchResults result={searchResult} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
