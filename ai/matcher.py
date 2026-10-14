import numpy as np


def cosine_similarity(embedding1, embedding2):
    """
    Returns similarity between two face embeddings.
    """

    if embedding1 is None or embedding2 is None:
        return 0.0

    similarity = np.dot(embedding1, embedding2)

    similarity /= (
        np.linalg.norm(embedding1)
        * np.linalg.norm(embedding2)
    )

    return float(similarity)


def is_match(embedding1, embedding2, threshold=0.50):
    """
    Returns:
        matched (True/False)
        similarity score
    """

    similarity = cosine_similarity(
        embedding1,
        embedding2
    )

    return similarity >= threshold, similarity