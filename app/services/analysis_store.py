import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

class AnalysisStore:
    def __init__(self) -> None:
        self.dir = os.getenv("ANALYSIS_DIR", "./analysis")
        os.makedirs(self.dir, exist_ok=True)
        self.index_path = os.path.join(self.dir, "index.jsonl")

    def save(
        self,
        result: Dict[str, Any],
        *,
        kind: str,
        device_id: Optional[str],
        command_id: Optional[str],
        image_path: Optional[str],
    ) -> Dict[str, Any]:
        ts = int(time.time() * 1000)
        analysis_id = str(uuid.uuid4())

        payload = dict(result)
        payload.update({
            "analysis_id": analysis_id,
            "created_ts_ms": ts,
            "kind": kind,
            "device_id": device_id,
            "command_id": command_id,
            "image_path": image_path,
        })

        result_path = os.path.join(self.dir, f"{ts}_{analysis_id}.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

        idx = {
            "analysis_id": analysis_id,
            "created_ts_ms": ts,
            "kind": kind,
            "device_id": device_id,
            "command_id": command_id,
            "image_path": image_path,
            "result_path": result_path,
        }
        with open(self.index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(idx, ensure_ascii=False) + "\n")

        return idx

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        if not os.path.exists(self.index_path):
            return []
        with open(self.index_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        out = []
        for ln in reversed(lines):
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
        return out

    def load(self, analysis_id: str) -> Dict[str, Any]:
        if not os.path.exists(self.index_path):
            raise FileNotFoundError("No analysis index found")
        path = None
        with open(self.index_path, "r", encoding="utf-8") as f:
            for ln in f:
                try:
                    rec = json.loads(ln)
                    if rec.get("analysis_id") == analysis_id:
                        path = rec.get("result_path")
                except Exception:
                    pass
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"analysis_id not found: {analysis_id}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

STORE = AnalysisStore()