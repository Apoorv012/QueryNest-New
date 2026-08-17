# Chunk Viewer (Dev Tool)

A React app for inspecting PDF extraction and chunking output. Not for production use.

## What It Shows

- **Upload**: Drag & drop a PDF to process
- **Chunk List**: All chunks with heading and text preview
- **Chunk Detail**: Full text + source blocks with page numbers and bounding boxes

## Setup

```bash
# Start the backend first
cd ../..
uvicorn core.api.main:app --reload

# Then start the frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`.

## How It Works

1. Upload a PDF via the UI
2. Backend runs extraction (pymupdf4llm) + chunking
3. View chunks in the sidebar
4. Click a chunk to see full text and source blocks

## Tech Stack

- React + TypeScript
- Vite
- Tailwind CSS
- Lucide React icons
