from typing import List
from .models import TextBlock

def extract_text_blocks(doc) -> List[TextBlock]:
    blocks: List[TextBlock] = []
    
    for page_number, page in enumerate(doc):
        page_dict = page.get_text("dict")
        
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
                            bbox=bbox
                        )
                    )
    
    return blocks