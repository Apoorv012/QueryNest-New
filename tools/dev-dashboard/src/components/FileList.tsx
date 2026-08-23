import { useState, useRef, useEffect } from 'react';
import type { DocumentInfo, JobStatus } from '../lib/api';
import { listDocuments, uploadFiles, getJobStatus } from '../lib/api';

interface Props {
  userId: string;
  documents: DocumentInfo[];
  onRefresh: () => void;
}

function formatMs(ms: number | null): string {
  if (ms === null) return '—';
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export function FileList({ userId, documents, onRefresh }: Props) {
  const [uploading, setUploading] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    const fileList = Array.from(files);

    try {
      const result = await uploadFiles(fileList, userId);
      const jobId = result.job_id;

      const poll = async () => {
        const status = await getJobStatus(jobId);
        setJob(status);
        if (status.status === 'processing') {
          pollRef.current = setTimeout(poll, 2000);
        } else {
          setUploading(false);
          onRefresh();
          pollRef.current = setTimeout(() => setJob(null), 4000);
        }
      };
      poll();
    } catch {
      setUploading(false);
    }

    if (fileInput.current) fileInput.current.value = '';
  };

  return (
    <div className="w-64 border-r bg-gray-50 p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-sm">Files ({documents.length})</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={onRefresh}
            disabled={uploading}
            className="text-gray-400 hover:text-gray-600 disabled:opacity-50"
            title="Refresh"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
            className="bg-blue-600 text-white text-xs px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : '+ Upload'}
          </button>
        </div>
        <input
          ref={fileInput}
          type="file"
          multiple
          accept=".pdf"
          onChange={handleUpload}
          className="hidden"
        />
      </div>

      {job && (
        <div className="mb-3 text-xs text-gray-600 bg-white rounded p-2 border">
          <div className="flex justify-between mb-1">
            <span>{job.status === 'processing' ? 'Processing...' : 'Done'}</span>
            <span>{job.completed}/{job.total}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div
              className="bg-blue-600 h-1.5 rounded-full transition-all"
              style={{ width: `${(job.completed / job.total) * 100}%` }}
            />
          </div>
          {job.status === 'processing' ? (
            <div className="mt-1 text-gray-400">
              {job.files.filter(f => f.status === 'done').length} done
              {job.failed > 0 && `, ${job.failed} failed`}
            </div>
          ) : (
            <ul className="mt-1 space-y-0.5">
              {job.files.map((f) => (
                <li key={f.filename} className="flex justify-between gap-2">
                  <span className="truncate" title={f.filename}>{f.filename}</span>
                  <span className={
                    f.status === 'error' ? 'text-red-500'
                    : f.was_duplicate ? 'text-amber-600'
                    : 'text-gray-400'
                  }>
                    {f.status === 'error' ? 'failed'
                      : f.was_duplicate ? 'already exists'
                      : formatMs(f.processing_ms)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-1">
        {documents.map((doc) => (
          <div
            key={doc.document_id}
            className="bg-white rounded border p-2 text-xs"
          >
            <div className="font-medium truncate" title={doc.filename}>
              {doc.filename}
            </div>
            <div className="text-gray-400 flex justify-between mt-1">
              <span>{doc.chunk_count} chunks</span>
              {doc.document_date ? (
                <span className="text-green-600">{doc.document_date}</span>
              ) : (
                <span className="text-gray-300">no date</span>
              )}
            </div>
          </div>
        ))}
        {documents.length === 0 && !uploading && (
          <div className="text-gray-400 text-xs text-center mt-8">
            No files uploaded yet
          </div>
        )}
      </div>
    </div>
  );
}
