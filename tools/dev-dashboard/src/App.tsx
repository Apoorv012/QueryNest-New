import { useState, useEffect, useCallback } from 'react';
import { UserSelector } from './components/UserSelector';
import { FileList } from './components/FileList';
import { SearchBar } from './components/SearchBar';
import { SearchResults } from './components/SearchResults';
import { listDocuments, search, seedGoldenSet, getSeedStatus, checkHealth } from './lib/api';
import type { DocumentInfo, SearchResponse } from './lib/api';

function App() {
  const [userId, setUserId] = useState('dev-user');
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedProgress, setSeedProgress] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const check = async () => setOnline(await checkHealth());
    check();
    const id = setInterval(check, 10000);
    return () => clearInterval(id);
  }, []);

  const refreshDocs = useCallback(async () => {
    try {
      const docs = await listDocuments(userId);
      setDocuments(docs);
    } catch {
      setDocuments([]);
    }
  }, [userId]);

  useEffect(() => {
    refreshDocs();
  }, [refreshDocs]);

  const handleSearch = async (query: string, dateFrom: string | null, dateTo: string | null) => {
    setSearching(true);
    try {
      const result = await search(query, userId, { dateFrom: dateFrom ?? undefined, dateTo: dateTo ?? undefined });
      setSearchResult(result);
    } catch {
      setSearchResult(null);
    }
    setSearching(false);
  };

  const handleSeed = async () => {
    setSeeding(true);
    setSeedProgress('Starting...');
    try {
      const result = await seedGoldenSet();
      if ('error' in result) {
        setSeedProgress(result.error);
        setSeeding(false);
        return;
      }
      const jobId = result.job_id;

      const poll = async () => {
        const status = await getSeedStatus(jobId);
        setSeedProgress(`${status.completed}/${status.total} indexed`);
        if (status.status === 'processing') {
          setTimeout(poll, 2000);
        } else {
          setSeedProgress(`Done: ${status.completed} indexed, ${status.failed} failed`);
          setSeeding(false);
          setUserId('golden_user');
        }
      };
      poll();
    } catch {
      setSeedProgress('Failed to start seeding');
      setSeeding(false);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-white">
      <header className="border-b px-4 py-2 flex items-center gap-4">
        <h1 className="font-bold text-sm">
          QueryNest <span className="bg-yellow-200 text-yellow-800 text-xs px-1.5 py-0.5 rounded ml-1">DEV</span>
        </h1>
        <UserSelector userId={userId} onUserChange={setUserId} />
        <div className="ml-auto flex items-center gap-2">
          <span className="flex items-center gap-1 text-xs">
            <span className={`w-2 h-2 rounded-full ${online === null ? 'bg-gray-300' : online ? 'bg-green-500' : 'bg-red-500'}`} />
            {online === null ? 'checking...' : online ? 'online' : 'offline'}
          </span>
          {seedProgress && (
            <span className="text-xs text-gray-500">{seedProgress}</span>
          )}
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="bg-amber-600 text-white text-xs px-3 py-1 rounded hover:bg-amber-700 disabled:opacity-50"
          >
            {seeding ? 'Seeding...' : 'Seed Golden Set'}
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <FileList userId={userId} documents={documents} onRefresh={refreshDocs} />

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
