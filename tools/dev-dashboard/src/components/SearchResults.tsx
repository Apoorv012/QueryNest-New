import type { SearchResponse } from '../lib/api';

interface Props {
  result: SearchResponse | null;
}

export function SearchResults({ result }: Props) {
  if (!result) {
    return (
      <div className="text-gray-400 text-sm text-center mt-16">
        Search for something to see results
      </div>
    );
  }

  if (result.results.length === 0) {
    return (
      <div className="text-gray-400 text-sm text-center mt-16">
        No results found
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-400 mb-2">
        Query: &quot;{result.parsed_query}&quot;
        {result.date_from && <span> from {result.date_from}</span>}
        {result.date_to && <span> to {result.date_to}</span>}
        <span> — {result.results.length} results</span>
      </div>

      {result.results.map((r, i) => (
        <div
          key={r.chunk_id}
          className="border rounded p-3 hover:bg-gray-50"
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">
              #{i + 1}
            </span>
            <span className="text-xs font-mono text-blue-600">
              {r.score.toFixed(3)}
            </span>
            {r.heading && (
              <span className="text-xs text-gray-500 font-medium">
                {r.heading}
              </span>
            )}
          </div>
          <div className="text-xs text-gray-400 mb-1">
            Page {r.page + 1}
            {r.document_date && <span> · {r.document_date}</span>}
          </div>
          <div className="text-sm text-gray-700 leading-relaxed">
            {r.text}
          </div>
        </div>
      ))}
    </div>
  );
}
