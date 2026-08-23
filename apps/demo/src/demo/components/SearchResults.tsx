import type { DateMatch, SearchResponse } from '../lib/api';
import { getPdfUrl, getPdfDownloadUrl } from '../lib/api';

interface Props {
  result: SearchResponse | null;
}

const TIER_HEADINGS: Partial<Record<DateMatch, string>> = {
  undated: 'No date on record — may or may not match',
  out_of_range: 'Outside the requested date range',
};

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

  const dateFilterApplied = Boolean(result.date_from || result.date_to);
  const wasRewritten = result.parsed_query !== result.query;
  let lastTier: DateMatch | null = null;

  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-400 mb-2 space-y-0.5">
        <div>
          Query: &quot;{result.parsed_query}&quot;
          <span> — {result.results.length} results</span>
        </div>
        {wasRewritten && (
          <div className="text-amber-600">
            Typed: &quot;{result.query}&quot; — date expression stripped before searching
          </div>
        )}
        {dateFilterApplied && (
          <div className="text-blue-600">
            Filtered to {result.date_from ?? '…'} → {result.date_to ?? '…'}
          </div>
        )}
      </div>

      {result.results.map((r, i) => {
        const showHeading =
          dateFilterApplied && r.date_match !== lastTier && TIER_HEADINGS[r.date_match];
        lastTier = r.date_match;

        return (
          <div key={r.chunk_id}>
            {showHeading && (
              <div className="text-xs uppercase tracking-wide text-gray-500 font-semibold mt-4 mb-2 pt-2 border-t">
                {TIER_HEADINGS[r.date_match]}
              </div>
            )}
            <div
              role="button"
              tabIndex={0}
              title={`Open ${r.filename} at page ${r.page + 1}`}
              onClick={() => window.open(`${getPdfUrl(r.document_id)}#page=${r.page + 1}`, '_blank')}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  window.open(`${getPdfUrl(r.document_id)}#page=${r.page + 1}`, '_blank');
                }
              }}
              className="border rounded p-3 hover:bg-gray-50 cursor-pointer"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">
                  #{i + 1}
                </span>
                <span className="text-xs font-mono text-blue-600">{r.score.toFixed(3)}</span>
                {r.heading && (
                  <span className="text-xs text-gray-500 font-medium">{r.heading}</span>
                )}
                <a
                  href={getPdfDownloadUrl(r.document_id)}
                  onClick={(e) => e.stopPropagation()}
                  title={`Download ${r.filename}`}
                  className="ml-auto text-xs text-gray-400 hover:text-blue-600 shrink-0"
                >
                  ⬇ Download
                </a>
              </div>
              <div className="text-xs text-gray-400 mb-1">
                {r.filename && <span className="text-gray-600">{r.filename}</span>}
                <span> · Page {r.page + 1}</span>
                {r.document_date && <span> · {r.document_date}</span>}
              </div>
              <div className="text-sm text-gray-700 leading-relaxed">{r.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
