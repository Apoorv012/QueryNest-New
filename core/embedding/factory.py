from core.embedding.base import BaseEmbedder
from core.embedding.local import LocalEmbedder


def get_embedder(use_cloud: bool = False, model_name: str = None) -> BaseEmbedder:
    """
    Factory: returns the appropriate embedder.

    Args:
        use_cloud: If True, use cloud-based embedding (not yet implemented).
        model_name: Override the default model name.

    Returns:
        A BaseEmbedder instance.

    Raises:
        NotImplementedError: If cloud embedding is requested.
    """
    if use_cloud:
        raise NotImplementedError(
            "Cloud embedding is not yet implemented. "
            "Set use_cloud=False to use local embedding."
        )

    kwargs = {}
    if model_name:
        kwargs["model_name"] = model_name

    return LocalEmbedder(**kwargs)
