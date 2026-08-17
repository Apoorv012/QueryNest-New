import type { ChunkData } from "./ChunkList";
import { FileText } from "lucide-react";

interface Props {
  chunk: ChunkData;
}

export function ChunkDetail({ chunk }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">{chunk.heading || "Untitled"}</h3>
        <p className="text-xs text-muted-foreground">
          Chunk {chunk.chunk_index} — {chunk.block_count} source blocks
        </p>
      </div>

      <div className="border rounded-md p-4 bg-muted/30">
        <p className="text-sm whitespace-pre-wrap leading-relaxed">{chunk.text}</p>
      </div>

      <div>
        <h4 className="text-sm font-semibold mb-2">Source Blocks</h4>
        <div className="space-y-2">
          {chunk.blocks.map((block, i) => (
            <div key={i} className="border rounded-md p-3 text-sm">
              <div className="flex items-center gap-2 mb-1">
                <FileText className="h-3 w-3 text-muted-foreground" />
                <span className="text-[10px] font-mono text-muted-foreground">
                  page {block.page + 1} | {block.type} | [{block.bbox.map((b) => b.toFixed(0)).join(", ")}]
                </span>
              </div>
              <p className="text-sm text-foreground/80">{block.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
