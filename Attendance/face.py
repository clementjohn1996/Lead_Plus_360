"""Server-side face detection (YuNet) and embedding (SFace) via OpenCV."""
import base64
import binascii
from functools import lru_cache
from pathlib import Path

import numpy as np
from django.conf import settings

MODEL_DIR = Path(__file__).resolve().parent / "face_models"
DETECTOR_MODEL = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = MODEL_DIR / "face_recognition_sface_2021dec.onnx"
MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_SIDE = 800


class FaceError(Exception):
    """A user-presentable problem with the submitted image."""


@lru_cache(maxsize=1)
def _models():
    import cv2

    if not (DETECTOR_MODEL.exists() and RECOGNIZER_MODEL.exists()):
        raise FaceError("Face recognition models are missing on the server.")
    detector = cv2.FaceDetectorYN.create(str(DETECTOR_MODEL), "", (320, 320), 0.7, 0.3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(str(RECOGNIZER_MODEL), "")
    return detector, recognizer


def decode_image(data_url):
    """Decode a base64 (optionally data-URL) JPEG/PNG into a BGR array."""
    import cv2

    if not data_url:
        raise FaceError("No photo was received.")
    payload = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    try:
        raw = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError):
        raise FaceError("The photo could not be read.")
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise FaceError("The photo is empty or too large.")
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise FaceError("The photo could not be read.")
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def encode_jpeg(img, quality=80):
    import cv2

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""


def extract_embedding(img):
    """Return (embedding, detection_score) for the most prominent face."""
    detector, recognizer = _models()
    h, w = img.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(img)
    if faces is None or len(faces) == 0:
        raise FaceError("No face detected. Face the camera in good light.")
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    best = faces[0]
    score = float(best[-1])
    if score < settings.FACE_MIN_DETECTION_SCORE:
        raise FaceError("Face not clear enough. Look straight at the camera.")
    if len(faces) > 1 and faces[1][2] * faces[1][3] > 0.35 * best[2] * best[3]:
        raise FaceError("More than one face detected. Only you should be in frame.")
    aligned = recognizer.alignCrop(img, best)
    feature = recognizer.feature(aligned).flatten().astype(np.float32)
    return feature.tolist(), score


def cosine(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def best_match(embedding, templates):
    """Highest cosine similarity between the embedding and stored embeddings."""
    return max((cosine(embedding, t) for t in templates), default=0.0)


def is_match(score):
    return score >= settings.FACE_COSINE_THRESHOLD
