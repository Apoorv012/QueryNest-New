import pymupdf
from typing import List
from core.models.text_block import TextBlock

def extract_text_blocks(doc: pymupdf.Document) -> List[TextBlock]:
    blocks: List[TextBlock] = []
    
    for page_number, page in enumerate(doc):
        page_dict = page.get_text("dict")
        page_height = page.rect.height
        
        for block in page_dict["blocks"]:
            if block["type"] != 0:
                continue
            
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    
                    bbox = tuple(span["bbox"])
                    blocks.append(
                        TextBlock(
                            text=text,
                            page=page_number,
                            bbox=bbox,
                            page_height=page_height
                        )
                    )
    
    return blocks