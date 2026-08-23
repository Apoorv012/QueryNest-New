import { useState } from 'react';

interface Props {
  onSearch: (query: string, dateFrom: string | null, dateTo: string | null) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: Props) {
  const [query, setQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(query, dateFrom || null, dateTo || null);
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-center">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search... (try 'what is rag' or 'berkshire report of 2023')"
        className="flex-1 border rounded px-3 py-2 text-sm"
      />
      <input
        type="date"
        value={dateFrom}
        onChange={(e) => setDateFrom(e.target.value)}
        className="border rounded px-2 py-2 text-xs text-gray-500 w-36"
        title="Date from (optional)"
      />
      <input
        type="date"
        value={dateTo}
        onChange={(e) => setDateTo(e.target.value)}
        className="border rounded px-2 py-2 text-xs text-gray-500 w-36"
        title="Date to (optional)"
      />
      <button
        type="submit"
        disabled={loading || !query.trim()}
        className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Searching...' : 'Search'}
      </button>
    </form>
  );
}
