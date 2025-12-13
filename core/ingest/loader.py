import pymupdf

def load_pdf(path: str):
    if not path.lower().endswith(".pdf"):
        raise ValueError("Only PDF supported for now")
    
    try:
        return pymupdf.open(path)
    except Exception as e:
        raise RuntimeError(f"Failed to load PDF: {e}")