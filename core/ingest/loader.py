import pymupdf

def load_pdf(path: str) -> pymupdf.Document:
    """
    Load a PDF file using PyMuPDF.
    
    Args:
        path: Absolute or the relative path to a .pdf file.
    
    Returns:
        PyMuPDF Document object.

    Raises:
        ValueError: If the file is not a PDF.
        RuntimeError: If the PDF cannot be loaded.
    """
    if not path.lower().endswith(".pdf"):
        raise ValueError(f"The path {path} is not a .pdf file")
    
    try:
        doc = pymupdf.open(path)
        return doc
    except Exception as e:
        raise RuntimeError(f"Failed to load PDF: {e}")