import React, { useCallback } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  onUpload: (file: File) => void;
  loading: boolean;
}

export function UploadZone({ onUpload, loading }: Props) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file?.type === "application/pdf") {
        onUpload(file);
      }
    },
    [onUpload]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onUpload(file);
    }
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
      className={cn(
        "border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors",
        "hover:border-foreground/40",
        loading ? "opacity-50 pointer-events-none" : ""
      )}
    >
      <Upload className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
      {loading ? (
        <div className="flex items-center justify-center gap-2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-foreground border-t-transparent" />
          <span className="text-muted-foreground">Extracting and chunking...</span>
        </div>
      ) : (
        <>
          <p className="text-sm font-medium">Drop a PDF here or click to upload</p>
          <p className="text-xs text-muted-foreground mt-1">.pdf files only</p>
        </>
      )}
      <input
        type="file"
        accept=".pdf"
        onChange={handleChange}
        className="hidden"
        id="file-upload"
      />
      {!loading && (
        <label
          htmlFor="file-upload"
          className="mt-4 inline-block text-xs text-muted-foreground cursor-pointer hover:underline"
        >
          or browse files
        </label>
      )}
    </div>
  );
}
