const API_BASE = '/api';

export interface DocumentInfo {
  document_id: string;
  filename: string;
  document_date: string | null;
  chunk_count: number;
}

export interface FileStatus {
  filename: string;
  status: string;
  document_id: string | null;
  detected_date: string | null;
  date_source: string | null;
  error: string | null;
  processing_ms: number | null;
}

export interface JobStatus {
  job_id: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
  files: FileStatus[];
}

export interface SourceBlock {
  text: string;
  page: number;
  bbox: number[];
  type: string;
}

export interface SearchResult {
  chunk_id: number;
  document_id: string;
  text: string;
  heading: string;
  score: number;
  page: number;
  document_date: string | null;
  source_blocks: SourceBlock[];
}

export interface SearchResponse {
  query: string;
  parsed_query: string;
  date_from: string | null;
  date_to: string | null;
  results: SearchResult[];
}

export async function listDocuments(userId: string): Promise<DocumentInfo[]> {
  const res = await fetch(`${API_BASE}/documents?user_id=${encodeURIComponent(userId)}`);
  const data = await res.json();
  return data.documents ?? [];
}

export async function uploadFiles(
  files: File[],
  userId: string,
): Promise<{ job_id: string; total: number }> {
  const form = new FormData();
  for (const f of files) {
    form.append('files', f);
  }
  const res = await fetch(`${API_BASE}/upload/bulk?user_id=${encodeURIComponent(userId)}`, {
    method: 'POST',
    body: form,
  });
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/upload/${jobId}/status`);
  return res.json();
}

export async function search(
  query: string,
  userId: string,
  options?: { dateFrom?: string; dateTo?: string; topK?: number },
): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      user_id: userId,
      date_from: options?.dateFrom ?? null,
      date_to: options?.dateTo ?? null,
      top_k: options?.topK ?? 5,
    }),
  });
  return res.json();
}

export async function updateDocumentDate(
  docId: string,
  userId: string,
  date: string | null,
): Promise<void> {
  await fetch(`${API_BASE}/documents/${docId}/date?user_id=${encodeURIComponent(userId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date }),
  });
}

export function getPdfUrl(docId: string, userId: string): string {
  return `${API_BASE}/documents/${docId}/pdf?user_id=${encodeURIComponent(userId)}`;
}

export async function seedGoldenSet(): Promise<{ job_id: string; total: number }> {
  const res = await fetch(`${API_BASE}/eval/seed`, { method: 'POST' });
  return res.json();
}

export async function getSeedStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/eval/seed/${jobId}/status`);
  return res.json();
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
