import cv2
import numpy as np
import os
import threading

from storage import resolve_upload_path


_model = None
_model_lock = threading.Lock()


def _get_model():
    """Load the CPU model only when matching is first requested."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from insightface.app import FaceAnalysis

                model_root = os.path.expanduser(
                    os.environ.get("INSIGHTFACE_HOME", "~/.insightface")
                )
                _model = FaceAnalysis(
                    name="buffalo_l",
                    root=model_root,
                    providers=["CPUExecutionProvider"],
                )
                _model.prepare(ctx_id=-1, det_size=(640, 640))
    return _model


def get_face_embedding(image_path):
    """
    Returns the face embedding of an image.
    Returns None if no face is detected.
    """

    resolved_path = resolve_upload_path(image_path)
    if not resolved_path or not os.path.exists(resolved_path):
        return None

    image = cv2.imread(resolved_path)

    if image is None:
        return None

    faces = _get_model().get(image)

    if len(faces) == 0:
        return None

    # Take the first detected face
    embedding = faces[0].embedding

    embedding = np.asarray(
        embedding,
        dtype=np.float32
    )

    norm = np.linalg.norm(embedding)
    if norm == 0:
        return None
    embedding = embedding / norm

    return embedding
