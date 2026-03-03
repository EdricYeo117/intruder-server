import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import torch
import torchvision.models as models

@dataclass
class AnalyzerConfig:
    reference_height_cm: float = float(os.getenv("REFERENCE_HEIGHT_CM", "170"))
    known_face_width_cm: float = float(os.getenv("KNOWN_FACE_WIDTH_CM", "16"))
    focal_length: float = float(os.getenv("FOCAL_LENGTH", "600"))
    fairface_ckpt: str = os.getenv("FAIRFACE_CKPT", "models/fairface_alldata_4race_20191111.pt")

AGES = ["0-2", "3-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70+"]

class HumanAnalyzer:
    def __init__(self, cfg: Optional[AnalyzerConfig] = None):
        self.cfg = cfg or AnalyzerConfig()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        mp_pose = mp.solutions.pose
        self.pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        mp_face = mp.solutions.face_detection
        self.face_detection = mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.6)

        if not os.path.exists(self.cfg.fairface_ckpt):
            raise FileNotFoundError(
                f"Missing FairFace checkpoint: {self.cfg.fairface_ckpt}. "
                f"Set FAIRFACE_CKPT or place it under intruder-server/models/."
            )

        model = models.resnet34(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, 18)

        state_dict = torch.load(self.cfg.fairface_ckpt, map_location=self.device)
        if isinstance(state_dict, dict) and "state_dict" in state_dict:
            state_dict = state_dict["state_dict"]
        if isinstance(state_dict, dict):
            state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}

        model.load_state_dict(state_dict, strict=True)
        model.to(self.device)
        model.eval()
        self.model = model

    @staticmethod
    def _clamp_bbox(x, y, w, h, img_w, img_h):
        x = max(0, x); y = max(0, y); w = max(1, w); h = max(1, h)
        if x + w > img_w: w = img_w - x
        if y + h > img_h: h = img_h - y
        return x, y, w, h

    def _predict_age_gender(self, face_bgr: np.ndarray) -> Tuple[str, str]:
        face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        face_rgb = cv2.resize(face_rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
        face_rgb = face_rgb.astype(np.float32) / 255.0
        x = torch.from_numpy(face_rgb).permute(2, 0, 1).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(x)[0]  # [18]

        gender_logits = logits[7:9]
        age_logits = logits[9:18]
        gender_idx = int(torch.argmax(gender_logits).item())
        age_idx = int(torch.argmax(age_logits).item())

        gender = "Male" if gender_idx == 0 else "Female"
        age = AGES[age_idx]
        return age, gender

    def _estimate_height(self, pose_landmarks, frame_h: int) -> float:
        head = pose_landmarks.landmark[0].y * frame_h
        foot = pose_landmarks.landmark[28].y * frame_h
        pixel = abs(foot - head)
        return round((pixel / frame_h) * self.cfg.reference_height_cm, 1)

    def _estimate_distance(self, face_width_pixels: int) -> float:
        face_width_pixels = max(1, int(face_width_pixels))
        return round((self.cfg.known_face_width_cm * self.cfg.focal_length) / face_width_pixels, 1)

    def analyze_bgr(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        t0 = time.time()
        frame_h, frame_w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        face_results = self.face_detection.process(rgb)
        faces = []
        if face_results.detections:
            for det in face_results.detections:
                bbox = det.location_data.relative_bounding_box
                x = int(bbox.xmin * frame_w)
                y = int(bbox.ymin * frame_h)
                w = int(bbox.width * frame_w)
                h = int(bbox.height * frame_h)
                x, y, w, h = self._clamp_bbox(x, y, w, h, frame_w, frame_h)
                faces.append((x, y, w, h))

        pose_result = self.pose.process(rgb)
        height_cm: Optional[float] = None
        if pose_result.pose_landmarks:
            height_cm = self._estimate_height(pose_result.pose_landmarks, frame_h)

        people: List[Dict[str, Any]] = []
        for (x, y, w, h) in faces:
            face_crop = frame_bgr[y:y + h, x:x + w]
            if face_crop.size == 0:
                continue
            try:
                age, gender = self._predict_age_gender(face_crop)
            except Exception:
                age, gender = "?", "?"
            people.append({
                "bbox_xywh": [x, y, w, h],
                "age": age,
                "gender": gender,
                "distance_cm": self._estimate_distance(w),
                "height_cm": height_cm,
            })

        return {
            "ok": True,
            "num_faces": len(people),
            "people": people,
            "latency_ms": int((time.time() - t0) * 1000),
            "device": self.device,
        }

    def analyze_image_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"ok": False, "error": "Could not decode image"}
        return self.analyze_bgr(frame)