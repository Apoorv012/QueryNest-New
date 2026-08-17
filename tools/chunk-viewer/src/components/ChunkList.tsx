import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";

export interface ChunkData {
  chunk_index: number;
  heading: string;
  text: string;
  block_count: number;
  blocks: {
    text: string;
    page: number;
    bbox: number[];
    type: string;
  }[];
}

interface Props {
  chunks: ChunkData[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}

export function ChunkList({ chunks, selectedIndex, onSelect }: Props) {
  return (
    <div className="space-y-1">
      <h2 className="text-sm font-semibold text-muted-foreground mb-2">
        {chunks.length} chunks
      </h2>
      <div className="space-y-1 max-h-[600px] overflow-y-auto">
        {chunks.map((chunk) => (
          <button
            key={chunk.chunk_index}
            onClick={() => onSelect(chunk.chunk_index)}
            className={cn(
              "w-full text-left p-3 rounded-md text-sm transition-colors",
              "hover:bg-accent",
              selectedIndex === chunk.chunk_index
                ? "bg-accent"
                : ""
            )}
          >
            <div className="flex items-center gap-2">
              <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
              <span className="font-medium truncate">{chunk.heading || "Untitled"}</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1 ml-5 line-clamp-2">
              {chunk.text.slice(0, 120)}...
            </p>
            <span className="text-[10px] text-muted-foreground ml-5">
              {chunk.block_count} blocks
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
