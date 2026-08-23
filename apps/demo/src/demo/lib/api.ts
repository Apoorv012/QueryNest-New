// Talks only to the lite public backend (core.api.public_main) — it exposes
// exactly GET /documents, GET /documents/{id}/pdf, POST /search, GET /health,
// all scoped to the golden demo corpus server-side. There is no user_id to
// pass and no upload/seed/edit endpoint to call.
const API_BASE = import.meta.env.VITE_API_BASE ?? '/api';

export interface DocumentInfo {
  document_id: string;
  filename: string;
  document_date: string | null;
  chunk_count: number;
}

export interface SourceBlock {
  text: string;
  page: number;
  bbox: number[];
  type: string;
}

export type DateMatch = 'in_range' | 'undated' | 'out_of_range' | 'unfiltered';

export interface SearchResult {
  chunk_id: number;
  document_id: string;
  filename: string;
  text: string;
  heading: string;
  score: number;
  page: number;
  document_date: string | null;
  source_blocks: SourceBlock[];
  date_match: DateMatch;
}

export interface SearchResponse {
  query: string;
  parsed_query: string;
  date_from: string | null;
  date_to: string | null;
  results: SearchResult[];
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${API_BASE}/documents`);
  const data = await res.json();
  return data.documents ?? [];
}

export async function search(
  query: string,
  options?: { dateFrom?: string; dateTo?: string; topK?: number },
): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      date_from: options?.dateFrom ?? null,
      date_to: options?.dateTo ?? null,
      top_k: options?.topK ?? 5,
    }),
  });
  return res.json();
}

export function getPdfUrl(docId: string): string {
  return `${API_BASE}/documents/${docId}/pdf`;
}

export function getPdfDownloadUrl(docId: string): string {
  return `${API_BASE}/documents/${docId}/pdf?download=true`;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}
