import base64
import hashlib
import hmac
import html
import io
import json
import mimetypes
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException
from redis import Redis
from sqlmodel import Session, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import engine
from aicoding_shared.models import (
    AgentRunStatus,
    AgentStepStatus,
    AuditLog,
    ModelCallLog,
    SafetyPolicy,
    VideoAudit,
    VideoAuditAgentRun,
    VideoAuditAgentStep,
    VideoAuditAlertEvent,
    VideoAuditEvidence,
    VideoAuditFinding,
    VideoMemorySegment,
    VideoAuditReport,
    VideoAuditStatus,
    VideoRiskLevel,
    now_utc,
)
from aicoding_shared.service import create_service_app
from aicoding_shared.storage import ObjectStorage


app = create_service_app("video-worker")

SAFE_LABELS = {"safe_walkway", "authorized_intervention", "closed_panel_cover", "safe_carrying"}
UNSAFE_LABELS = {"walkway_violation", "unauthorized_intervention", "opened_panel_cover", "forklift_overload"}
ALL_LABELS = SAFE_LABELS | UNSAFE_LABELS
RISK_LEVELS = {item.value for item in VideoRiskLevel}
LABEL_TEXT = {
    "safe_walkway": "人员在安全通道内通行",
    "authorized_intervention": "授权人员按流程操作设备",
    "closed_panel_cover": "设备护罩/柜门保持关闭",
    "safe_carrying": "物料搬运方式安全",
    "walkway_violation": "人员进入非安全通道或危险区域",
    "unauthorized_intervention": "疑似未授权干预设备",
    "opened_panel_cover": "设备护罩/柜门处于打开状态",
    "forklift_overload": "叉车或搬运设备疑似超载/不规范搬运",
}
RECOMMENDATIONS = {
    "walkway_violation": "立即复核现场通道标识和隔离措施，要求人员按安全通道通行。",
    "unauthorized_intervention": "核验作业许可和上锁挂牌流程，未授权操作需立即停工整改。",
    "opened_panel_cover": "检查设备护罩、柜门和联锁装置，恢复防护后再继续作业。",
    "forklift_overload": "复核叉车载重和物料固定方式，必要时拆分搬运并重新培训司机。",
}
DEFAULT_REVIEW_RECOMMENDATION = "该片段置信度不足、画面质量不足或语义不明确，建议安全主管人工复核。"
RISK_LEVEL_TEXT = {
    VideoRiskLevel.low: "低风险",
    VideoRiskLevel.medium: "中风险",
    VideoRiskLevel.high: "高风险",
    VideoRiskLevel.critical: "严重风险",
    VideoRiskLevel.needs_review: "需人工复核",
}


SAFETY_SKILL_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "prompts" / "safety_inspection_skill.md",
    Path(__file__).resolve().parents[3] / "prompts" / "safety_inspection_skill.md",
    Path(__file__).resolve().parent / "prompts" / "safety_inspection_skill.md",
]


def load_safety_skill_prompt() -> str:
    for path in SAFETY_SKILL_CANDIDATES:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError("safety_inspection_skill.md was not found")


class VisionSafetyAnalyzer:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.vision_base_url or self.settings.llm_base_url
        self.api_key = self.settings.vision_api_key or self.settings.llm_api_key
        self.model = self.settings.vision_model or self.settings.llm_model
        self.raw_outputs: list[str] = []

    def available(self) -> bool:
        return bool(self.settings.vision_enabled and self.base_url and self.api_key and self.model)

    async def analyze(self, frame_paths: list[Path], source_name: str, duration_ms: int) -> tuple[list[dict], dict]:
        if not self.available():
            raise RuntimeError("Vision model is not configured")
        selected = self._select_frames(frame_paths)
        if not selected:
            raise RuntimeError("No frames available for vision analysis")
        all_events: list[dict] = []
        batch_size = max(1, int(self.settings.vision_frame_batch_size))
        for start in range(0, len(selected), batch_size):
            batch = selected[start : start + batch_size]
            content = await self._call_vision_model(batch, source_name, duration_ms)
            self.raw_outputs.append(content)
            parsed = parse_vision_events(content)
            for event in parsed:
                event["frame_index"] = self._nearest_frame_index(event, batch)
                all_events.append(normalize_vision_event(event, duration_ms))
        meta = {
            "analysis_provider": "vision-llm",
            "analysis_model": self.model,
            "frames_analyzed": len(selected),
            "vision_raw_outputs": self.raw_outputs,
            "fallback_reason": "",
        }
        return all_events, meta

    def _select_frames(self, frame_paths: list[Path]) -> list[tuple[int, Path, int]]:
        max_frames = max(1, int(self.settings.vision_max_frames))
        interval_ms = int(self.settings.video_audit_frame_interval_seconds * 1000)
        if len(frame_paths) <= max_frames:
            indices = list(range(len(frame_paths)))
        else:
            step = (len(frame_paths) - 1) / (max_frames - 1)
            indices = sorted({round(i * step) for i in range(max_frames)})
        return [(index, frame_paths[index], index * interval_ms) for index in indices]

    async def _call_vision_model(self, batch: list[tuple[int, Path, int]], source_name: str, duration_ms: int) -> str:
        user_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "请执行安全巡检 Skill。下面是同一段工业/仓储巡检视频的抽帧图片。"
                    f"视频时长：{duration_ms} ms。"
                    "请只依据图片内容判断，不要依据文件名或路径推断类别。"
                    "每张图片前会给出 frame_index 和 timestamp_ms。"
                    "严禁复制 Skill 文档中的任何示例坐标、示例文案或固定答案。"
                    "如发现明确风险，请返回 bbox 字段框出当前图片中最小的关键风险主体；"
                    "如果只能框出大面积无关区域，请返回 bbox=null 并标记 needs_review。"
                    "bbox、reason 和 evidence_caption 必须描述同一个对象；框住物料就只能描述物料风险，框住人员才可以描述人员风险。"
                    "不要仅因为看不清 PPE 或未见授权标识就判定未授权干预，证据不足时标记 needs_review。"
                    "如果人员靠近设备或坐在设备旁，但无法确认是否授权、是否佩戴 PPE、设备是否运行，请输出 risk_level=needs_review 的复核项，不要直接判 high，也不要忽略该可疑场景。"
                    "请按 Skill 规定返回严格 JSON。"
                ),
            }
        ]
        for index, path, timestamp_ms in batch:
            user_content.append({"type": "text", "text": f"frame_index={index}, timestamp_ms={timestamp_ms}"})
            user_content.append({"type": "image_url", "image_url": {"url": image_data_url(path)}})
        async with httpx.AsyncClient(timeout=self.settings.vision_timeout_seconds) as client:
            resp = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": load_safety_skill_prompt()},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _nearest_frame_index(self, event: dict, batch: list[tuple[int, Path, int]]) -> int:
        timestamp = int(event.get("timestamp_ms") or event.get("start_ms") or 0)
        return min(batch, key=lambda item: abs(item[2] - timestamp))[0]


class SafetyClassifier:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = None
        self.labels = list(LABEL_TEXT)
        self.device = "cpu"
        self.model_version = "rule-fallback"
        self._load_model()

    def _load_model(self) -> None:
        model_path = Path(self.settings.video_audit_model_path)
        if not model_path.exists():
            return
        try:
            import torch
            from torchvision.models.video import r3d_18

            if self.settings.video_audit_device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self.device = self.settings.video_audit_device
            checkpoint = torch.load(model_path, map_location=self.device)
            self.labels = checkpoint.get("labels", self.labels)
            model = r3d_18(weights=None, num_classes=len(self.labels))
            model.load_state_dict(checkpoint["model_state"])
            model.to(self.device)
            model.eval()
            self.model = model
            self.model_version = checkpoint.get("model_version", model_path.name)
        except Exception:
            self.model = None
            self.model_version = "rule-fallback"

    def classify_windows(self, video_path: Path, frame_paths: list[Path], source_name: str) -> tuple[list[dict], dict]:
        if self.model is not None and frame_paths:
            try:
                return self._classify_with_model(frame_paths), {
                    "analysis_provider": "local-r3d18",
                    "analysis_model": self.model_version,
                    "frames_analyzed": len(frame_paths),
                    "vision_raw_outputs": [],
                    "fallback_reason": "",
                }
            except Exception as exc:
                return self._classify_with_rules(frame_paths, source_name), {
                    "analysis_provider": "rule-fallback",
                    "analysis_model": "rule-fallback",
                    "frames_analyzed": len(frame_paths),
                    "vision_raw_outputs": [],
                    "fallback_reason": f"local-r3d18 failed: {exc}",
                }
        return self._classify_with_rules(frame_paths, source_name), {
            "analysis_provider": "rule-fallback",
            "analysis_model": "rule-fallback",
            "frames_analyzed": len(frame_paths),
            "vision_raw_outputs": [],
            "fallback_reason": "local model is unavailable",
        }

    def _classify_with_model(self, frame_paths: list[Path]) -> list[dict]:
        import torch
        from PIL import Image
        from torchvision.transforms import v2

        interval = self.settings.video_audit_frame_interval_seconds
        transform = v2.Compose([
            v2.Resize((128, 171)),
            v2.CenterCrop((112, 112)),
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=[0.43216, 0.394666, 0.37645], std=[0.22803, 0.22145, 0.216989]),
        ])
        results: list[dict] = []
        window_size = 16
        step = 8
        for start in range(0, max(len(frame_paths) - 1, 1), step):
            selected = frame_paths[start : start + window_size]
            if not selected:
                continue
            while len(selected) < window_size:
                selected.append(selected[-1])
            tensors = [transform(Image.open(path).convert("RGB")) for path in selected]
            video = torch.stack(tensors, dim=1).unsqueeze(0).to(self.device)
            with torch.no_grad():
                probs = torch.softmax(self.model(video), dim=1)[0]
            score, index = torch.max(probs, dim=0)
            label = self.labels[int(index)]
            results.append({
                "label": label,
                "confidence": float(score),
                "start_ms": int(start * interval * 1000),
                "end_ms": int((start + len(selected)) * interval * 1000),
                "frame_index": min(start + len(selected) // 2, len(frame_paths) - 1),
            })
        return results

    def _classify_with_rules(self, frame_paths: list[Path], source_name: str) -> list[dict]:
        lower = source_name.lower()
        label = "safe_walkway"
        confidence = 0.52
        if any(token in lower for token in ["forklift_overload", "forklift-overload", "overload"]):
            label = "forklift_overload"
            confidence = 0.68
        elif any(token in lower for token in ["unauthorized_intervention", "unauthorized-intervention", "unauthorized", "unsafe_intervention"]):
            label = "unauthorized_intervention"
            confidence = 0.62
        elif any(token in lower for token in ["opened_panel_cover", "opened-panel-cover", "open_panel", "open-panel", "opened panel", "open cover"]):
            label = "opened_panel_cover"
            confidence = 0.6
        elif any(token in lower for token in ["walkway_violation", "walkway-violation", "violation", "danger", "unsafe_walkway"]):
            label = "walkway_violation"
            confidence = 0.6
        elif any(token in lower for token in ["authorized_intervention", "authorized-intervention"]):
            label = "authorized_intervention"
            confidence = 0.58
        elif any(token in lower for token in ["closed_panel_cover", "closed-panel-cover", "closed cover"]):
            label = "closed_panel_cover"
            confidence = 0.58
        elif any(token in lower for token in ["safe_carrying", "safe-carrying", "safe carrying"]):
            label = "safe_carrying"
            confidence = 0.58
        elif any(token in lower for token in ["safe_walkway", "safe-walkway", "safe walkway"]):
            label = "safe_walkway"
            confidence = 0.58
        frame_index = max(len(frame_paths) // 2, 0)
        return [{
            "label": label,
            "confidence": confidence,
            "start_ms": 0,
            "end_ms": int(max(len(frame_paths), 1) * self.settings.video_audit_frame_interval_seconds * 1000),
            "frame_index": frame_index,
        }]


def image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{media_type};base64,{encoded}"


def parse_vision_events(content: str) -> list[dict]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = min([idx for idx in [text.find("{"), text.find("[")] if idx >= 0], default=-1)
        end = max(text.rfind("}"), text.rfind("]"))
        if start < 0 or end <= start:
            raise
        payload = json.loads(text[start : end + 1])
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        findings = payload.get("findings") or payload.get("risks") or payload.get("events") or []
        if isinstance(findings, list):
            return findings
    raise ValueError("Vision response must contain a findings array")


def normalize_vision_event(event: dict, duration_ms: int) -> dict:
    settings = get_settings()
    raw_label = str(event.get("label") or "").strip()
    label = raw_label if raw_label in ALL_LABELS else "safe_walkway"
    confidence = clamp_float(event.get("confidence"), 0.0, 1.0, 0.0)
    timestamp_ms = clamp_int(event.get("timestamp_ms"), 0, duration_ms, 0)
    start_ms = clamp_int(event.get("start_ms"), 0, duration_ms, max(0, timestamp_ms - int(settings.video_audit_window_seconds * 500)))
    end_ms = clamp_int(event.get("end_ms"), 0, duration_ms, min(duration_ms or start_ms + 1000, timestamp_ms + int(settings.video_audit_window_seconds * 500)))
    if end_ms <= start_ms:
        end_ms = min(duration_ms or start_ms + 1000, start_ms + 1000)
    raw_risk = str(event.get("risk_level") or "").strip()
    risk = VideoRiskLevel(raw_risk) if raw_risk in RISK_LEVELS else _risk_for(label, confidence)
    if label in SAFE_LABELS and risk not in {VideoRiskLevel.low, VideoRiskLevel.needs_review}:
        risk = VideoRiskLevel.low
    if raw_label not in ALL_LABELS:
        risk = VideoRiskLevel.needs_review
    reason = str(event.get("reason") or LABEL_TEXT.get(label, "视觉模型无法确认该片段。"))
    recommendation = str(event.get("recommendation") or RECOMMENDATIONS.get(label, DEFAULT_REVIEW_RECOMMENDATION))
    caption = str(event.get("evidence_caption") or reason)
    if not _has_chinese(reason):
        reason = LABEL_TEXT.get(label, reason)
    if not _has_chinese(recommendation):
        recommendation = RECOMMENDATIONS.get(label, recommendation)
    if not _has_chinese(caption):
        caption = reason
    bbox = normalize_bbox(event.get("bbox"))
    bbox_issue = _bbox_quality_issue(label, bbox)
    if bbox_issue:
        risk = VideoRiskLevel.needs_review
        reason = f"{bbox_issue}，当前画面需要安全主管结合原视频复核。"
        recommendation = DEFAULT_REVIEW_RECOMMENDATION
        caption = bbox_issue
    if risk == VideoRiskLevel.needs_review:
        recommendation = DEFAULT_REVIEW_RECOMMENDATION
    return {
        "label": label,
        "risk_level": risk,
        "confidence": confidence,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "timestamp_ms": timestamp_ms,
        "bbox": bbox,
        "frame_index": int(event.get("frame_index") or 0),
        "reason": reason,
        "recommendation": recommendation,
        "evidence_caption": caption,
    }


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def normalize_bbox(value: Any) -> list[int] | None:
    if isinstance(value, dict):
        value = [
            value.get("x_min", value.get("xmin", value.get("left"))),
            value.get("y_min", value.get("ymin", value.get("top"))),
            value.get("x_max", value.get("xmax", value.get("right"))),
            value.get("y_max", value.get("ymax", value.get("bottom"))),
        ]
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = [int(round(float(item))) for item in value]
    except (TypeError, ValueError):
        return None
    x1, x2 = sorted((max(0, min(1000, x1)), max(0, min(1000, x2))))
    y1, y2 = sorted((max(0, min(1000, y1)), max(0, min(1000, y2))))
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    return [x1, y1, x2, y2]


def _bbox_quality_issue(label: str, bbox: list[int] | None) -> str:
    if label not in UNSAFE_LABELS:
        return ""
    if bbox is None:
        return "模型未能给出可靠的风险定位框"
    area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / 1_000_000
    if area_ratio < 0.005:
        return "模型给出的风险定位框过小，疑似目标定位不稳定"
    if area_ratio > 0.45:
        return "模型给出的风险定位框过大，包含过多无关区域"
    return ""


def clamp_float(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    if maximum <= 0:
        return max(minimum, parsed)
    return max(minimum, min(maximum, parsed))


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def _ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _duration_from_ffmpeg(video_path: Path) -> int:
    result = subprocess.run([_ffmpeg_executable(), "-i", str(video_path)], capture_output=True, text=True, check=False)
    text = f"{result.stderr}\n{result.stdout}"
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return 0
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return int((hours * 3600 + minutes * 60 + seconds) * 1000)


def _duration_ms(video_path: Path) -> int:
    try:
        output = _run([
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ])
        return int(float(output or "0") * 1000)
    except Exception:
        return _duration_from_ffmpeg(video_path)


def _extract_frames(video_path: Path, frame_dir: Path) -> list[Path]:
    interval = max(get_settings().video_audit_frame_interval_seconds, 0.5)
    try:
        _run([
            _ffmpeg_executable(),
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{interval}",
            "-q:v",
            "3",
            str(frame_dir / "frame_%06d.jpg"),
        ])
        frames = sorted(frame_dir.glob("frame_*.jpg"))
        if frames:
            return frames
        return [_write_placeholder_frame(frame_dir, "ffmpeg produced no frames")]
    except Exception as exc:
        return [_write_placeholder_frame(frame_dir, str(exc) or "ffmpeg is unavailable")]


def _write_placeholder_frame(frame_dir: Path, reason: str) -> Path:
    frame_path = frame_dir / "frame_000001.svg"
    safe_reason = html.escape(reason[:180])
    frame_path.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#111827"/>
  <rect x="64" y="64" width="1152" height="592" rx="12" fill="#1f2937" stroke="#64748b" stroke-width="2"/>
  <text x="640" y="320" text-anchor="middle" font-family="Arial, sans-serif" font-size="34" fill="#f8fafc">Video frame unavailable</text>
  <text x="640" y="370" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" fill="#cbd5e1">Install ffmpeg for real evidence screenshots.</text>
  <text x="640" y="420" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#94a3b8">{safe_reason}</text>
</svg>
""",
        encoding="utf-8",
    )
    return frame_path


def _risk_for(label: str, confidence: float) -> VideoRiskLevel:
    settings = get_settings()
    if confidence < settings.video_audit_confidence_threshold:
        return VideoRiskLevel.needs_review
    if label == "forklift_overload":
        return VideoRiskLevel.critical
    if label in UNSAFE_LABELS:
        return VideoRiskLevel.high
    return VideoRiskLevel.low


def _overall_risk(levels: list[VideoRiskLevel]) -> VideoRiskLevel:
    if VideoRiskLevel.critical in levels:
        return VideoRiskLevel.critical
    if VideoRiskLevel.high in levels:
        return VideoRiskLevel.high
    if VideoRiskLevel.needs_review in levels:
        return VideoRiskLevel.needs_review
    if VideoRiskLevel.medium in levels:
        return VideoRiskLevel.medium
    return VideoRiskLevel.low


def _risk_value(risk: VideoRiskLevel | str) -> str:
    return risk.value if isinstance(risk, VideoRiskLevel) else str(risk)


def _risk_text(risk: VideoRiskLevel | str) -> str:
    if isinstance(risk, str):
        try:
            risk = VideoRiskLevel(risk)
        except ValueError:
            return risk
    return RISK_LEVEL_TEXT.get(risk, _risk_value(risk))


FALLBACK_POLICY_BY_LABEL: dict[str, dict[str, Any]] = {
    "walkway_violation": {
        "title": "安全通道占用处置策略",
        "due_hours": 2,
        "auto_alert": True,
        "requires_review": False,
        "recommend_ticket": True,
        "requires_verification": True,
    },
    "unauthorized_intervention": {
        "title": "未授权设备干预处置策略",
        "due_hours": 4,
        "auto_alert": True,
        "requires_review": True,
        "recommend_ticket": True,
        "requires_verification": True,
    },
    "opened_panel_cover": {
        "title": "设备防护打开处置策略",
        "due_hours": 4,
        "auto_alert": True,
        "requires_review": False,
        "recommend_ticket": True,
        "requires_verification": True,
    },
    "forklift_overload": {
        "title": "叉车和搬运超载处置策略",
        "due_hours": 1,
        "auto_alert": True,
        "requires_review": False,
        "recommend_ticket": True,
        "requires_verification": True,
    },
}


def _policies_for_findings(session: Session, tenant_id: int, findings: list[VideoAuditFinding]) -> list[SafetyPolicy]:
    labels = sorted({item.label for item in findings})
    if not labels:
        return []
    return session.exec(
        select(SafetyPolicy).where(
            SafetyPolicy.tenant_id == tenant_id,
            SafetyPolicy.enabled == True,  # noqa: E712
            SafetyPolicy.label.in_(labels),
        )
    ).all()


def _policy_value(policy_by_label: dict[str, SafetyPolicy], label: str, key: str, default: Any) -> Any:
    policy = policy_by_label.get(label)
    if policy is not None and hasattr(policy, key):
        return getattr(policy, key)
    return FALLBACK_POLICY_BY_LABEL.get(label, {}).get(key, default)


def _decide_safety_action(
    audit: VideoAudit,
    findings: list[VideoAuditFinding],
    policies: list[SafetyPolicy],
    processing_ms: int = 0,
) -> dict:
    policy_by_label = {item.label: item for item in policies}
    labels = sorted({item.label for item in findings})
    levels = [item.risk_level for item in findings]
    high_or_critical = audit.risk_level in {VideoRiskLevel.high, VideoRiskLevel.critical}
    needs_review = audit.risk_level == VideoRiskLevel.needs_review or any(item.risk_level == VideoRiskLevel.needs_review for item in findings)
    due_hours = min(
        [_policy_value(policy_by_label, label, "due_hours", 24) for label in labels],
        default=0,
    )
    requires_verification = any(_policy_value(policy_by_label, label, "requires_verification", False) for label in labels)
    recommend_ticket = any(_policy_value(policy_by_label, label, "recommend_ticket", False) for label in labels)
    send_alert = bool(
        findings
        and (high_or_critical or needs_review)
        and any(_policy_value(policy_by_label, label, "auto_alert", False) for label in labels)
    )
    if not findings:
        reason = "未检测到明确风险，Agent 不触发告警或整改工单。"
    elif needs_review:
        reason = "检测到证据不足但值得关注的风险片段，Agent 触发人工复核提醒。"
    elif high_or_critical:
        reason = "检测到明确高风险或严重风险，Agent 触发飞书告警并建议创建整改工单。"
    else:
        reason = "检测到一般隐患，Agent 建议现场确认后整改。"
    return {
        "overall_risk": _risk_value(audit.risk_level),
        "send_feishu_alert": send_alert,
        "needs_human_review": needs_review,
        "recommend_ticket": bool((recommend_ticket or high_or_critical) and not needs_review),
        "requires_verification": bool(requires_verification),
        "recommended_due_hours": int(due_hours),
        "decision_reason": reason,
        "matched_policy_titles": [
            _policy_value(policy_by_label, label, "title", FALLBACK_POLICY_BY_LABEL.get(label, {}).get("title", label))
            for label in labels
        ],
        "processing_ms": processing_ms,
        "risk_levels": [_risk_value(item) for item in levels],
    }


def _record_agent_step(
    session: Session,
    run: VideoAuditAgentRun,
    step_order: int,
    tool_name: str,
    input_summary: str,
    output_summary: str,
    detail: dict | None = None,
    latency_ms: int = 0,
    status: AgentStepStatus = AgentStepStatus.completed,
    error: str = "",
    artifact_refs: list[dict] | None = None,
) -> None:
    run.current_step = tool_name
    run.current_stage = tool_name
    session.add(run)
    session.add(VideoAuditAgentStep(
        tenant_id=run.tenant_id,
        audit_id=run.audit_id,
        run_id=run.id or 0,
        step_order=step_order,
        tool_name=tool_name,
        status=status,
        input_summary=input_summary,
        output_summary=output_summary,
        detail=detail or {},
        artifact_refs=artifact_refs or [],
        latency_ms=latency_ms,
        error=error,
    ))
    session.flush()


def _raw_frame_memory_key(audit: VideoAudit, frame_path: Path) -> str:
    return f"tenant-{audit.tenant_id}/audits/{audit.id}/memory/{frame_path.name}"


def _store_raw_frame_memory(storage: ObjectStorage, audit: VideoAudit, frames: list[Path]) -> list[dict]:
    refs: list[dict] = []
    for index, frame_path in enumerate(frames):
        key = _raw_frame_memory_key(audit, frame_path)
        storage.put_bytes(key, frame_path.read_bytes(), ObjectStorage().content_type(frame_path.name))
        refs.append({"frame_index": index, "object_key": key})
    return refs


def _alert_risk_levels() -> set[str]:
    return {
        item.strip()
        for item in get_settings().feishu_alert_risk_levels.split(",")
        if item.strip()
    }


def _should_send_feishu_alert(audit: VideoAudit) -> bool:
    settings = get_settings()
    return bool(
        settings.feishu_alert_enabled
        and settings.feishu_webhook_url
        and _risk_value(audit.risk_level) in _alert_risk_levels()
    )


def _feishu_sign(secret: str, timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _build_feishu_alert_text(audit: VideoAudit, findings: list[VideoAuditFinding]) -> str:
    is_review = audit.risk_level == VideoRiskLevel.needs_review
    lines = [
        "【安全巡检复核提醒】" if is_review else "【安全巡检告警】",
        f"任务编号：#{audit.id}",
        f"视频文件：{audit.file_name}",
        f"风险等级：{_risk_text(audit.risk_level)}",
        f"风险摘要：{audit.summary or '发现安全异常，请尽快复核。'}",
    ]
    if findings:
        lines.append("风险时间轴：")
        for item in findings[:5]:
            lines.append(
                f"- {item.start_ms // 1000}s-{item.end_ms // 1000}s："
                f"{LABEL_TEXT.get(item.label, item.label)}，置信度 {round(item.confidence * 100)}%。"
            )
    if len(findings) > 5:
        lines.append(f"- 另有 {len(findings) - 5} 个风险片段，请在系统内查看。")
    if is_review:
        lines.append("处置建议：请安全主管先复核原视频、证据截图和现场记录，确认后再决定是否派发整改工单。")
    else:
        lines.append("处置建议：请安全主管立即打开系统查看证据截图，确认风险后派发整改工单。")
    lines.append("系统说明：该消息由视频巡检 Agent 自动触发，模型结果需结合原视频和现场情况复核。")
    return "\n".join(lines)


async def _send_feishu_safety_alert(
    audit: VideoAudit,
    findings: list[VideoAuditFinding],
    session: Session,
) -> dict:
    if not _should_send_feishu_alert(audit):
        return {"status": "skipped", "reason": "alert policy disabled or risk level not configured"}
    settings = get_settings()
    message = _build_feishu_alert_text(audit, findings)
    payload: dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": message},
    }
    if settings.feishu_webhook_secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _feishu_sign(settings.feishu_webhook_secret, timestamp)
    try:
        async with httpx.AsyncClient(timeout=settings.feishu_alert_timeout_seconds) as client:
            resp = await client.post(settings.feishu_webhook_url, json=payload)
            resp.raise_for_status()
        session.add(AuditLog(
            tenant_id=audit.tenant_id,
            actor_id=audit.uploader_id,
            action="video_audit.feishu_alert_sent",
            target_type="video_audit",
            target_id=str(audit.id),
            detail={
                "risk_level": _risk_value(audit.risk_level),
                "findings": len(findings),
                "channel": "feishu",
            },
        ))
        session.add(VideoAuditAlertEvent(
            tenant_id=audit.tenant_id,
            audit_id=audit.id,
            channel="feishu",
            status="sent",
            risk_level=audit.risk_level,
            message=message,
        ))
        return {"status": "sent", "channel": "feishu"}
    except Exception as exc:
        error = str(exc)[:500]
        session.add(AuditLog(
            tenant_id=audit.tenant_id,
            actor_id=audit.uploader_id,
            action="video_audit.feishu_alert_failed",
            target_type="video_audit",
            target_id=str(audit.id),
            detail={
                "risk_level": _risk_value(audit.risk_level),
                "findings": len(findings),
                "channel": "feishu",
                "error": error,
            },
        ))
        session.add(VideoAuditAlertEvent(
            tenant_id=audit.tenant_id,
            audit_id=audit.id,
            channel="feishu",
            status="failed",
            risk_level=audit.risk_level,
            message=message,
            error=error,
        ))
        return {"status": "failed", "channel": "feishu", "error": error}


def _annotate_evidence_frame(frame_path: Path, result: dict) -> tuple[bytes, str, str]:
    bbox = normalize_bbox(result.get("bbox"))
    if not bbox:
        return frame_path.read_bytes(), ObjectStorage().content_type(frame_path.name), frame_path.suffix or ".jpg"
    try:
        from PIL import Image, ImageDraw

        image = Image.open(frame_path).convert("RGB")
        width, height = image.size
        x1 = int(bbox[0] / 1000 * width)
        y1 = int(bbox[1] / 1000 * height)
        x2 = int(bbox[2] / 1000 * width)
        y2 = int(bbox[3] / 1000 * height)
        line_width = max(3, min(width, height) // 180)
        draw = ImageDraw.Draw(image)
        draw.rectangle([x1, y1, x2, y2], outline=(220, 38, 38), width=line_width)

        output = io.BytesIO()
        image.save(output, format="JPEG", quality=92)
        return output.getvalue(), "image/jpeg", ".jpg"
    except Exception:
        return frame_path.read_bytes(), ObjectStorage().content_type(frame_path.name), frame_path.suffix or ".jpg"


def _merge_risk_windows(results: list[dict], duration_ms: int) -> list[dict]:
    merged: list[dict] = []
    max_gap_ms = int(get_settings().video_audit_window_seconds * 1000)
    for result in sorted(results, key=lambda item: (int(item["start_ms"]), str(item["label"]))):
        label = str(result["label"])
        confidence = float(result["confidence"])
        risk = result.get("risk_level") or _risk_for(label, confidence)
        if isinstance(risk, str):
            risk = VideoRiskLevel(risk) if risk in RISK_LEVELS else _risk_for(label, confidence)
        if risk == VideoRiskLevel.low and label in SAFE_LABELS:
            continue
        start_ms = max(int(result["start_ms"]), 0)
        end_ms = min(max(int(result["end_ms"]), start_ms + 1000), duration_ms or int(result["end_ms"]))
        frame_index = int(result.get("frame_index", 0))
        if merged and merged[-1]["label"] == label and start_ms - int(merged[-1]["end_ms"]) <= max_gap_ms:
            previous = merged[-1]
            previous["end_ms"] = max(int(previous["end_ms"]), end_ms)
            previous["confidence"] = max(float(previous["confidence"]), confidence)
            previous["risk_level"] = _overall_risk([previous["risk_level"], risk])
            if confidence >= float(previous.get("evidence_confidence", 0)):
                previous["frame_index"] = frame_index
                previous["evidence_confidence"] = confidence
                previous["reason"] = result.get("reason", previous.get("reason", ""))
                previous["recommendation"] = result.get("recommendation", previous.get("recommendation", ""))
                previous["evidence_caption"] = result.get("evidence_caption", previous.get("evidence_caption", ""))
                previous["bbox"] = result.get("bbox", previous.get("bbox"))
            continue
        merged.append({
            "label": label,
            "confidence": confidence,
            "evidence_confidence": confidence,
            "risk_level": risk,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "frame_index": frame_index,
            "reason": result.get("reason", LABEL_TEXT.get(label, label)),
            "recommendation": result.get("recommendation", RECOMMENDATIONS.get(label, DEFAULT_REVIEW_RECOMMENDATION)),
            "evidence_caption": result.get("evidence_caption", LABEL_TEXT.get(label, label)),
            "bbox": result.get("bbox"),
        })
    return merged


async def _generate_report(
    audit: VideoAudit,
    findings: list[VideoAuditFinding],
    model_version: str,
    processing_ms: int,
    session: Session,
    analysis_meta: dict,
    agent_decision: dict | None = None,
    policies: list[SafetyPolicy] | None = None,
) -> dict:
    findings_payload = [
        {
            "label": item.label,
            "label_text": LABEL_TEXT.get(item.label, item.label),
            "risk_level": _risk_value(item.risk_level),
            "risk_level_text": _risk_text(item.risk_level),
            "confidence": round(item.confidence, 3),
            "start_seconds": item.start_ms // 1000,
            "end_seconds": item.end_ms // 1000,
            "bbox": getattr(item, "bbox", None),
            "reason": item.reason,
            "recommendation": item.recommendation,
        }
        for item in findings
    ]
    report = {
        "audit_id": audit.id,
        "file_name": audit.file_name,
        "risk_level": _risk_value(audit.risk_level),
        "risk_level_text": _risk_text(audit.risk_level),
        "summary": audit.summary,
        "findings": findings_payload,
        "recommend_ticket": audit.risk_level in {VideoRiskLevel.high, VideoRiskLevel.critical, VideoRiskLevel.needs_review},
        "model_version": model_version,
        "processing_ms": processing_ms,
        "review_notice": "模型结果用于巡检辅助决策，高风险与低置信度结果建议人工复核。",
        "agent_decision": agent_decision or {},
        "matched_policies": [
            {
                "code": item.code,
                "label": item.label,
                "title": item.title,
                "due_hours": item.due_hours,
                "requires_verification": item.requires_verification,
            }
            for item in (policies or [])
        ],
        **analysis_meta,
    }
    report["llm_report"] = _template_report(audit, findings)
    settings = get_settings()
    if not (settings.llm_base_url and settings.llm_api_key):
        return report
    start = time.perf_counter()
    prompt = (
        "请基于以下工业/仓储安全巡检视频识别结果生成简洁中文整改报告。\n"
        "格式要求：\n"
        "1. 不要使用 Markdown 表格、# 标题、加粗符号或分隔线。\n"
        "2. 只输出四段，段落标题固定为：总体结论、关键风险、整改建议、复核提示。\n"
        "3. 每段不超过 3 句，整改建议可以使用 1. 2. 3. 编号。\n"
        "4. 不要输出英文标签，风险等级和风险说明全部使用中文。\n"
        "5. 只基于给定证据，不要补充未观察到的事实。\n\n"
        f"结构化识别结果：\n{json.dumps(report, ensure_ascii=False)}"
    )
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": "你是企业安全巡检助手。输出必须简洁、中文、可执行，不使用 Markdown 表格。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            content = str(resp.json()["choices"][0]["message"].get("content") or "").strip()
            if content:
                report["llm_report"] = content
            else:
                report["llm_error"] = "LLM returned empty report content"
            session.add(ModelCallLog(
                tenant_id=audit.tenant_id,
                provider="openai-compatible",
                model=settings.llm_model,
                prompt_version="安全巡检报告:v1",
                input_summary=prompt[:200],
                output_summary=content[:200],
                latency_ms=int((time.perf_counter() - start) * 1000),
                prompt_tokens=len(prompt),
                completion_tokens=len(content),
            ))
    except Exception as exc:
        report["llm_error"] = str(exc)
    return report


def _template_report(audit: VideoAudit, findings: list[VideoAuditFinding]) -> str:
    if not findings:
        return "总体结论：未发现明确安全风险。建议继续保持现场通道、设备防护和物料摆放巡检。"
    lines = [
        f"总体结论：本次视频巡检发现 {len(findings)} 个风险片段，最高风险等级为{_risk_text(audit.risk_level)}。",
        "风险时间轴：",
    ]
    for item in findings:
        lines.append(
            f"- {item.start_ms // 1000}s-{item.end_ms // 1000}s：{LABEL_TEXT.get(item.label, item.label)}，"
            f"置信度 {round(item.confidence * 100)}%。{item.reason}"
        )
    lines.append("整改建议：")
    for item in findings:
        lines.append(f"- {item.recommendation}")
    lines.append("人工复核提示：模型结果用于安全巡检辅助决策，请安全主管结合原视频和现场情况复核。")
    return "\n".join(lines)


async def classify_with_fallback(video_path: Path, frames: list[Path], file_name: str, duration_ms: int) -> tuple[list[dict], dict]:
    vision = VisionSafetyAnalyzer()
    fallback_reason = ""
    if vision.available():
        try:
            return await vision.analyze(frames, file_name, duration_ms)
        except Exception as exc:
            fallback_reason = f"vision-llm failed: {exc}"
    else:
        fallback_reason = "vision model is not configured"
    classifier = SafetyClassifier()
    results, meta = classifier.classify_windows(video_path, frames, file_name)
    if fallback_reason:
        existing = meta.get("fallback_reason")
        meta["fallback_reason"] = f"{fallback_reason}; {existing}" if existing else fallback_reason
    return results, meta


async def process_audit(audit_id: int) -> dict:
    start = time.perf_counter()
    storage = ObjectStorage()
    with Session(engine) as session:
        audit = session.get(VideoAudit, audit_id)
        if audit is None:
            raise HTTPException(status_code=404, detail="Video audit not found")
        audit.status = VideoAuditStatus.processing
        audit.updated_at = now_utc()
        session.add(audit)
        session.flush()
        old_reports = session.exec(select(VideoAuditReport).where(VideoAuditReport.audit_id == audit.id)).all()
        old_findings = session.exec(select(VideoAuditFinding).where(VideoAuditFinding.audit_id == audit.id)).all()
        old_evidence = session.exec(select(VideoAuditEvidence).where(VideoAuditEvidence.audit_id == audit.id)).all()
        old_memory = session.exec(select(VideoMemorySegment).where(VideoMemorySegment.audit_id == audit.id)).all()
        old_alerts = session.exec(select(VideoAuditAlertEvent).where(VideoAuditAlertEvent.audit_id == audit.id)).all()
        old_runs = session.exec(select(VideoAuditAgentRun).where(VideoAuditAgentRun.audit_id == audit.id)).all()
        old_run_ids = [item.id for item in old_runs if item.id is not None]
        old_steps = []
        if old_run_ids:
            old_steps = session.exec(select(VideoAuditAgentStep).where(VideoAuditAgentStep.run_id.in_(old_run_ids))).all()
        for item in [*old_reports, *old_evidence, *old_findings, *old_memory, *old_alerts, *old_steps, *old_runs]:
            session.delete(item)
        run = VideoAuditAgentRun(
            tenant_id=audit.tenant_id,
            audit_id=audit.id,
            status=AgentRunStatus.running,
            goal="视频输入 -> 视频记忆 -> 视觉 grounding -> 风险决策 -> 告警/复核/工单 -> 闭环建议",
            current_stage="receive_task",
        )
        session.add(run)
        session.flush()
        step_order = 1
        _record_agent_step(
            session,
            run,
            step_order,
            "receive_task",
            f"audit_id={audit.id}, file={audit.file_name}",
            "已接收视频巡检任务并进入处理状态。",
            {"object_key": audit.object_key, "why": "启动一次可追踪的安全巡检 AgentRun。"},
        )
        session.commit()

        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                video_path = tmp_path / audit.file_name
                tool_start = time.perf_counter()
                video_path.write_bytes(storage.get_bytes(audit.object_key))
                frame_dir = tmp_path / "frames"
                frame_dir.mkdir()
                audit.duration_ms = _duration_ms(video_path)
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "load_video",
                    audit.object_key,
                    f"视频已加载，时长 {audit.duration_ms // 1000}s。",
                    {"duration_ms": audit.duration_ms, "why": "先读取视频元数据，后续所有时间线和证据截图都基于该视频。"},
                    int((time.perf_counter() - tool_start) * 1000),
                )
                tool_start = time.perf_counter()
                frames = _extract_frames(video_path, frame_dir)
                if not frames:
                    raise RuntimeError("No frames could be extracted from the video")
                frame_refs = _store_raw_frame_memory(storage, audit, frames)
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "sample_video_frames",
                    f"interval={get_settings().video_audit_frame_interval_seconds}s",
                    f"抽取 {len(frames)} 张关键帧。",
                    {"frames": len(frames), "why": "用固定间隔抽帧构建视频时间线，降低 VLM 调用成本。"},
                    int((time.perf_counter() - tool_start) * 1000),
                    artifact_refs=frame_refs[:12],
                )
                tool_start = time.perf_counter()
                window_results, analysis_meta = await classify_with_fallback(video_path, frames, audit.file_name, audit.duration_ms)
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "inspect_safety_frame",
                    f"frames={len(frames)}, model={analysis_meta.get('analysis_model')}",
                    f"获得 {len(window_results)} 条帧级视觉结果。",
                    {
                        "analysis_provider": analysis_meta.get("analysis_provider"),
                        "analysis_model": analysis_meta.get("analysis_model"),
                        "fallback_reason": analysis_meta.get("fallback_reason"),
                        "why": "调用视觉大模型识别风险主体、时间点和 bbox。",
                    },
                    int((time.perf_counter() - tool_start) * 1000),
                )
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "validate_bbox",
                    "校验 VLM 输出 bbox 与风险主体一致性。",
                    f"{sum(1 for item in window_results if item.get('bbox'))} 条结果包含 bbox。",
                    {
                        "with_bbox": sum(1 for item in window_results if item.get("bbox")),
                        "needs_review": sum(1 for item in window_results if item.get("risk_level") == VideoRiskLevel.needs_review),
                        "why": "bbox 是证据截图和人工复核的核心定位信息，缺失或异常时降低为复核项。",
                    },
                )
                tool_start = time.perf_counter()
                risk_events = _merge_risk_windows(window_results, audit.duration_ms)
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "merge_risk_events",
                    f"frame_level_results={len(window_results)}",
                    f"合并为 {len(risk_events)} 个风险事件。",
                    {"risk_events": len(risk_events), "why": "相邻同类风险合并，避免同一隐患重复告警。"},
                    int((time.perf_counter() - tool_start) * 1000),
                )

                findings: list[VideoAuditFinding] = []
                raw_result_by_frame: dict[int, list[dict]] = {}
                for result in window_results:
                    raw_result_by_frame.setdefault(int(result.get("frame_index", 0)), []).append(result)
                interval_ms = int(get_settings().video_audit_frame_interval_seconds * 1000)
                for frame_index, frame_path in enumerate(frames):
                    raw_results = raw_result_by_frame.get(frame_index, [])
                    visible_objects = sorted({
                        LABEL_TEXT.get(str(item.get("label")), str(item.get("label")))
                        for item in raw_results
                        if item.get("label")
                    })
                    first_result = raw_results[0] if raw_results else {}
                    session.add(VideoMemorySegment(
                        tenant_id=audit.tenant_id,
                        audit_id=audit.id,
                        start_ms=frame_index * interval_ms,
                        end_ms=min(audit.duration_ms or (frame_index + 1) * interval_ms, (frame_index + 1) * interval_ms),
                        frame_index=frame_index,
                        frame_object_key=_raw_frame_memory_key(audit, frame_path),
                        visible_objects=visible_objects,
                        risk_subject=LABEL_TEXT.get(str(first_result.get("label")), "") if first_result else "",
                        bbox=first_result.get("bbox") if first_result else None,
                        evidence=str(first_result.get("reason") or "关键帧已抽取，未发现明确风险主体。"),
                        raw_finding=dict(first_result) if first_result else {},
                        vlm_raw_output={"findings": raw_results, "analysis_model": analysis_meta.get("analysis_model")},
                        review_status="needs_review" if any(item.get("risk_level") == VideoRiskLevel.needs_review for item in raw_results) else "unreviewed",
                    ))
                for result in risk_events:
                    label = result["label"]
                    confidence = float(result["confidence"])
                    risk = result["risk_level"]
                    finding = VideoAuditFinding(
                        tenant_id=audit.tenant_id,
                        audit_id=audit.id,
                        label=label,
                        risk_level=risk,
                        confidence=confidence,
                        start_ms=int(result["start_ms"]),
                        end_ms=int(result["end_ms"]),
                        bbox=result.get("bbox"),
                        reason=result.get("reason") or LABEL_TEXT.get(label, label),
                        recommendation=result.get("recommendation") or RECOMMENDATIONS.get(label, DEFAULT_REVIEW_RECOMMENDATION),
                    )
                    session.add(finding)
                    session.flush()
                    frame_index = min(max(int(result.get("frame_index", 0)), 0), len(frames) - 1)
                    frame_path = frames[frame_index]
                    evidence_bytes, evidence_content_type, evidence_suffix = _annotate_evidence_frame(frame_path, result)
                    frame_key = (
                        f"tenant-{audit.tenant_id}/audits/{audit.id}/evidence/"
                        f"{frame_path.stem}_finding_{finding.id}_{label}_annotated{evidence_suffix}"
                    )
                    storage.put_bytes(frame_key, evidence_bytes, evidence_content_type)
                    evidence = VideoAuditEvidence(
                        tenant_id=audit.tenant_id,
                        audit_id=audit.id,
                        finding_id=finding.id,
                        timestamp_ms=int(frame_index * get_settings().video_audit_frame_interval_seconds * 1000),
                        frame_object_key=frame_key,
                        caption=result.get("evidence_caption") or f"{LABEL_TEXT.get(label, label)}，置信度 {confidence:.2f}",
                        model_score=confidence,
                    )
                    session.add(evidence)
                    raw_finding = dict(result)
                    raw_finding["risk_level"] = _risk_value(raw_finding.get("risk_level", ""))
                    session.add(VideoMemorySegment(
                        tenant_id=audit.tenant_id,
                        audit_id=audit.id,
                        start_ms=int(result["start_ms"]),
                        end_ms=int(result["end_ms"]),
                        frame_index=frame_index,
                        frame_object_key=frame_key,
                        visible_objects=[LABEL_TEXT.get(label, label)],
                        risk_subject=LABEL_TEXT.get(label, label),
                        bbox=result.get("bbox"),
                        evidence=result.get("reason") or LABEL_TEXT.get(label, label),
                        raw_finding=raw_finding,
                        vlm_raw_output=raw_finding,
                        review_status="needs_review" if risk == VideoRiskLevel.needs_review else "risk",
                    ))
                    findings.append(finding)
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "build_video_memory",
                    f"frames={len(frames)}, risk_events={len(risk_events)}",
                    f"写入 {len(frames)} 个关键帧记忆和 {len(risk_events)} 个风险证据记忆。",
                    {
                        "frame_memory_segments": len(frames),
                        "risk_memory_segments": len(risk_events),
                        "why": "先保存视频结构化记忆，再让 Agent 基于记忆做风险决策和复核展示。",
                    },
                )

                levels = [item.risk_level for item in findings]
                audit.risk_level = _overall_risk(levels)
                if not findings:
                    audit.risk_level = VideoRiskLevel.low
                    audit.summary = "未检测到明确不安全行为。"
                elif audit.risk_level == VideoRiskLevel.needs_review:
                    audit.summary = "检测结果置信度不足或视觉证据不明确，建议人工复核。"
                else:
                    audit.summary = f"发现 {len(findings)} 个安全风险片段，最高风险等级为{_risk_text(audit.risk_level)}。"
                audit.status = VideoAuditStatus.needs_review if audit.risk_level == VideoRiskLevel.needs_review else VideoAuditStatus.completed
                audit.completed_at = now_utc()
                audit.updated_at = now_utc()
                processing_ms = int((time.perf_counter() - start) * 1000)
                model_version = str(analysis_meta.get("analysis_model") or "unknown")
                policies = _policies_for_findings(session, audit.tenant_id, findings)
                agent_decision = _decide_safety_action(audit, findings, policies, processing_ms)
                run.decision = agent_decision
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "decide_safety_action",
                    f"overall_risk={_risk_value(audit.risk_level)}",
                    agent_decision["decision_reason"],
                    agent_decision,
                )
                tool_start = time.perf_counter()
                report = await _generate_report(audit, findings, model_version, processing_ms, session, analysis_meta, agent_decision, policies)
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "write_audit_report",
                    f"findings={len(findings)}",
                    "已生成结构化中文审核报告。",
                    {"model_version": model_version, "why": "把视觉证据和策略决策整理成安全主管可阅读的中文报告。"},
                    int((time.perf_counter() - tool_start) * 1000),
                )
                session.add(VideoAuditReport(
                    tenant_id=audit.tenant_id,
                    audit_id=audit.id,
                    report=report,
                    model_version=model_version,
                    processing_ms=processing_ms,
                ))
                tool_start = time.perf_counter()
                alert_result = await _send_feishu_safety_alert(audit, findings, session)
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "send_feishu_alert",
                    f"send_feishu_alert={agent_decision['send_feishu_alert']}",
                    f"飞书告警状态：{alert_result.get('status')}",
                    alert_result,
                    int((time.perf_counter() - tool_start) * 1000),
                )
                step_order += 1
                _record_agent_step(
                    session,
                    run,
                    step_order,
                    "recommend_remediation_ticket",
                    f"recommend_ticket={agent_decision['recommend_ticket']}",
                    "已生成整改工单建议，等待主管确认创建。" if agent_decision["recommend_ticket"] else "当前不建议直接创建整改工单。",
                    {
                        "recommend_ticket": agent_decision["recommend_ticket"],
                        "requires_verification": agent_decision["requires_verification"],
                        "recommended_due_hours": agent_decision["recommended_due_hours"],
                        "why": "整改工单由主管确认创建，避免模型误报直接派单。",
                    },
                )
                session.add(AuditLog(
                    tenant_id=audit.tenant_id,
                    actor_id=audit.uploader_id,
                    action="video_audit.completed",
                    target_type="video_audit",
                    target_id=str(audit.id),
                    detail={
                        "risk_level": audit.risk_level,
                        "findings": len(findings),
                        "analysis_provider": analysis_meta.get("analysis_provider"),
                        "analysis_model": analysis_meta.get("analysis_model"),
                    },
                ))
                run.final_decision = agent_decision
                if agent_decision.get("needs_human_review"):
                    run.status = AgentRunStatus.waiting_review
                    run.paused_reason = "等待安全主管人工复核模型证据。"
                    run.current_step = "waiting_review"
                    run.current_stage = "waiting_review"
                elif agent_decision.get("recommend_ticket"):
                    run.status = AgentRunStatus.waiting_remediation
                    run.paused_reason = "等待主管创建整改工单并上传整改后证据。"
                    run.current_step = "waiting_remediation"
                    run.current_stage = "waiting_remediation"
                else:
                    run.status = AgentRunStatus.completed
                    run.completed_at = now_utc()
                    run.current_step = "completed"
                    run.current_stage = "completed"
                session.add(run)
                session.add(audit)
                session.commit()
                return {"status": audit.status, "audit_id": audit.id, "findings": len(findings), "risk_level": _risk_value(audit.risk_level)}
        except Exception as exc:
            audit.status = VideoAuditStatus.failed
            audit.error = str(exc)[:1000]
            audit.updated_at = now_utc()
            run.status = AgentRunStatus.failed
            run.error = audit.error
            run.completed_at = now_utc()
            session.add(run)
            step_order += 1
            _record_agent_step(
                session,
                run,
                step_order,
                "agent_failed",
                f"audit_id={audit.id}",
                "Agent 执行失败。",
                {},
                status=AgentStepStatus.failed,
                error=audit.error,
            )
            session.add(audit)
            session.add(AuditLog(
                tenant_id=audit.tenant_id,
                actor_id=audit.uploader_id,
                action="video_audit.failed",
                target_type="video_audit",
                target_id=str(audit.id),
                detail={"error": audit.error},
            ))
            session.commit()
            return {"status": "failed", "audit_id": audit.id, "error": audit.error}


@app.post("/tasks/video-audits/process/{audit_id}")
async def process_one(audit_id: int):
    return await process_audit(audit_id)


@app.post("/tasks/video-audits/process-next")
async def process_next():
    item = _redis().lpop(get_settings().video_audit_queue)
    if item is None:
        return {"status": "idle"}
    payload = json.loads(item)
    return await process_audit(int(payload["audit_id"]))
