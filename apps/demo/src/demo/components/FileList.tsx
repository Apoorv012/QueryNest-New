import type { DocumentInfo } from '../lib/api';
import { Disabled } from './Disabled';

interface Props {
  documents: DocumentInfo[];
}

export function FileList({ documents }: Props) {
  return (
    <div className="w-64 border-r bg-gray-50 p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-sm">Files ({documents.length})</h2>
        <Disabled message="Read-only demo — upload disabled" direction="down">
          <button className="bg-blue-600 text-white text-xs px-3 py-1 rounded">
            + Upload
          </button>
        </Disabled>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1">
        {documents.map((doc) => (
          <div key={doc.document_id} className="bg-white rounded border p-2 text-xs">
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
        {documents.length === 0 && (
          <div className="text-gray-400 text-xs text-center mt-8">Loading corpus…</div>
        )}
      </div>
    </div>
  );
}
