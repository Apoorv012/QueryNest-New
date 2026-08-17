import { useState } from "react";
import { UploadZone } from "@/components/UploadZone";
import { ChunkList, type ChunkData } from "@/components/ChunkList";
import { ChunkDetail } from "@/components/ChunkDetail";
import { FileSearch } from "lucide-react";

function App() {
  const [loading, setLoading] = useState(false);
  const [chunks, setChunks] = useState<ChunkData[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [filename, setFilename] = useState("");

  const handleUpload = async (file: File) => {
    setLoading(true);
    setChunks([]);
    setSelectedIndex(null);

    const form = new FormData();
    form.append("file", file);

    const res = await fetch("/api/upload", { method: "POST", body: form });
    const data = await res.json();

    if (data.error) {
      alert(data.error);
      setLoading(false);
      return;
    }

    setFilename(data.filename);

    const chunkRes = await fetch(`/api/documents/${data.id}/chunks`);
    const chunkData = await chunkRes.json();
    setChunks(chunkData.chunks);
    setLoading(false);
  };

  const selectedChunk = selectedIndex !== null ? chunks[selectedIndex] : null;

  return (
    <div className="min-h-screen">
      <header className="border-b px-6 py-4">
        <div className="flex items-center gap-2">
          <FileSearch className="h-5 w-5" />
          <h1 className="text-lg font-semibold">QueryNest</h1>
          <span className="text-[10px] font-mono bg-yellow-100 text-yellow-800 px-1.5 py-0.5 rounded">
            DEV
          </span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {chunks.length === 0 && !loading ? (
          <div className="max-w-md mx-auto mt-20">
            <UploadZone onUpload={handleUpload} loading={loading} />
          </div>
        ) : (
          <div className="grid grid-cols-[350px_1fr] gap-6">
            <div>
              <div className="mb-4 text-sm text-muted-foreground">
                {filename}
              </div>
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground mt-8">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-foreground border-t-transparent" />
                  Processing PDF...
                </div>
              ) : (
                <ChunkList
                  chunks={chunks}
                  selectedIndex={selectedIndex}
                  onSelect={setSelectedIndex}
                />
              )}
            </div>
            <div>
              {selectedChunk ? (
                <ChunkDetail chunk={selectedChunk} />
              ) : (
                <div className="text-center text-muted-foreground mt-40">
                  Select a chunk to view details
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
