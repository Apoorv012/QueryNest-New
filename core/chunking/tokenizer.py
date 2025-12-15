def estimate_tokens(text: str) -> int:
    """
    Rough token estimate.
    Good enough for v1 chunking.
    """
    return int(len(text.split()) * 1.3)
