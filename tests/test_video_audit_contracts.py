import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))


def test_video_audit_models_have_expected_defaults():
    code = """
from aicoding_shared.models import AgentRunStatus, TicketVerification, TicketVerificationStatus, VideoAudit, VideoAuditAgentRun, VideoAuditAgentStep, VideoMemorySegment, VideoAuditStatus, VideoRiskLevel
audit = VideoAudit(tenant_id=1, file_name='sample.mp4', object_key='tenant-1/audits/sample.mp4')
assert audit.status == VideoAuditStatus.queued
assert VideoAuditStatus.needs_review == 'needs_review'
assert audit.risk_level == VideoRiskLevel.needs_review
assert audit.duration_ms == 0
run = VideoAuditAgentRun(tenant_id=1, audit_id=1)
assert run.status == AgentRunStatus.running
assert AgentRunStatus.waiting_review == 'waiting_review'
assert AgentRunStatus.waiting_remediation == 'waiting_remediation'
assert run.final_decision == {}
step = VideoAuditAgentStep(tenant_id=1, audit_id=1, run_id=1, step_order=1, tool_name='sample_video_frames')
assert step.artifact_refs == []
memory = VideoMemorySegment(tenant_id=1, audit_id=1)
assert memory.review_status == 'unreviewed'
verification = TicketVerification(tenant_id=1, ticket_id=1, object_key='tenant-1/tickets/1/verification/pass.jpg')
assert verification.status == TicketVerificationStatus.needs_review
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "shared")
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_agent_decision_policy_recommends_alert_ticket_and_verification():
    code = """
from app.main import _decide_safety_action
from aicoding_shared.models import VideoAudit, VideoAuditFinding, VideoRiskLevel

audit = VideoAudit(
    tenant_id=1,
    file_name='walkway_violation.mp4',
    object_key='tenant-1/audits/source.mp4',
    risk_level=VideoRiskLevel.high,
)
finding = VideoAuditFinding(
    tenant_id=1,
    audit_id=1,
    label='walkway_violation',
    risk_level=VideoRiskLevel.high,
    confidence=0.92,
)
decision = _decide_safety_action(audit, [finding], [], 1234)
assert decision['overall_risk'] == 'high'
assert decision['send_feishu_alert'] is True
assert decision['recommend_ticket'] is True
assert decision['requires_verification'] is True
assert decision['recommended_due_hours'] == 2
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'video-worker'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_agent_decision_needs_review_does_not_recommend_ticket():
    code = """
from app.main import _decide_safety_action
from aicoding_shared.models import VideoAudit, VideoAuditFinding, VideoRiskLevel

audit = VideoAudit(
    tenant_id=1,
    file_name='uncertain_intervention.mp4',
    object_key='tenant-1/audits/source.mp4',
    risk_level=VideoRiskLevel.needs_review,
)
finding = VideoAuditFinding(
    tenant_id=1,
    audit_id=1,
    label='unauthorized_intervention',
    risk_level=VideoRiskLevel.needs_review,
    confidence=0.65,
)
decision = _decide_safety_action(audit, [finding], [], 100)
assert decision['needs_human_review'] is True
assert decision['recommend_ticket'] is False
assert decision['send_feishu_alert'] is True
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'video-worker'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_ticket_verification_filename_strategy():
    code = """
from app.main import _evaluate_verification_file
from aicoding_shared.models import TicketVerificationStatus

assert _evaluate_verification_file('after_pass.jpg')[0] == TicketVerificationStatus.passed
assert _evaluate_verification_file('still_unsafe.mp4')[0] == TicketVerificationStatus.failed
assert _evaluate_verification_file('现场复检.jpg')[0] == TicketVerificationStatus.needs_review
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'ticket-service'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_local_object_storage_roundtrip(tmp_path):
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_LOCAL_ROOT"] = str(tmp_path)

    from aicoding_shared.config import get_settings
    from aicoding_shared.storage import ObjectStorage

    get_settings.cache_clear()
    storage = ObjectStorage()
    storage.put_bytes("tenant-1/audits/frame.jpg", b"image-bytes", "image/jpeg")

    assert storage.exists("tenant-1/audits/frame.jpg")
    assert storage.get_bytes("tenant-1/audits/frame.jpg") == b"image-bytes"
    assert storage.content_type("tenant-1/audits/frame.jpg") == "image/jpeg"


def test_adjacent_risk_windows_merge():
    code = """
from app.main import _merge_risk_windows
merged = _merge_risk_windows(
    [
        {'label': 'walkway_violation', 'confidence': 0.6, 'start_ms': 0, 'end_ms': 4000, 'frame_index': 1},
        {'label': 'walkway_violation', 'confidence': 0.8, 'start_ms': 5000, 'end_ms': 9000, 'frame_index': 3},
        {'label': 'opened_panel_cover', 'confidence': 0.7, 'start_ms': 20000, 'end_ms': 24000, 'frame_index': 10},
    ],
    duration_ms=30000,
)
assert len(merged) == 2
assert merged[0]['label'] == 'walkway_violation'
assert merged[0]['start_ms'] == 0
assert merged[0]['end_ms'] == 9000
assert merged[0]['confidence'] == 0.8
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'video-worker'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_vision_response_parsing_and_unknown_label_review():
    code = """
from app.main import parse_vision_events, normalize_vision_event
from aicoding_shared.models import VideoRiskLevel
events = parse_vision_events('```json\\n{\"findings\":[{\"label\":\"unknown\",\"risk_level\":\"high\",\"confidence\":0.9,\"timestamp_ms\":1000}]}\\n```')
normalized = normalize_vision_event(events[0], 5000)
assert normalized['label'] == 'safe_walkway'
assert normalized['risk_level'] == VideoRiskLevel.needs_review
assert normalized['start_ms'] <= normalized['timestamp_ms'] <= normalized['end_ms']
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'video-worker'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_vision_needs_review_risk_is_not_promoted_to_high():
    code = """
from app.main import normalize_vision_event
from aicoding_shared.models import VideoRiskLevel

event = {
    'label': 'unauthorized_intervention',
    'risk_level': 'needs_review',
    'confidence': 0.86,
    'timestamp_ms': 1000,
    'start_ms': 0,
    'end_ms': 2000,
    'bbox': [100, 100, 240, 420],
    'reason': '人员靠近设备，但无法确认授权、PPE 和设备运行状态。',
    'recommendation': '请安全主管结合原视频和现场作业记录复核。',
    'evidence_caption': '人员位于设备旁，需复核作业状态。',
}
normalized = normalize_vision_event(event, 5000)
assert normalized['label'] == 'unauthorized_intervention'
assert normalized['risk_level'] == VideoRiskLevel.needs_review
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'video-worker'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_vision_contract_risk_level_is_preserved_after_schema_validation():
    code = """
from app.main import normalize_vision_event
from aicoding_shared.models import VideoRiskLevel

medium = normalize_vision_event({
    'label': 'walkway_violation',
    'risk_level': 'medium',
    'confidence': 0.78,
    'timestamp_ms': 1000,
    'start_ms': 0,
    'end_ms': 2000,
    'bbox': [300, 300, 420, 450],
    'reason': '通道边缘存在临时物料，仍保留部分通行空间，需要现场确认是否影响通行。',
    'recommendation': '复核现场通道宽度和物料暂存位置，必要时移至指定暂存区。',
    'evidence_caption': '通道边缘存在临时物料。',
}, 5000)
assert medium['risk_level'] == VideoRiskLevel.medium

review = normalize_vision_event({
    'label': 'unauthorized_intervention',
    'risk_level': 'needs_review',
    'confidence': 0.91,
    'timestamp_ms': 1000,
    'start_ms': 0,
    'end_ms': 2000,
    'bbox': [100, 100, 240, 420],
    'reason': '人员坐在设备旁，但无法确认授权、PPE 和设备运行状态。',
    'recommendation': '请安全主管复核。',
    'evidence_caption': '人员位于设备旁。',
}, 5000)
assert review['risk_level'] == VideoRiskLevel.needs_review

strong = normalize_vision_event({
    'label': 'walkway_violation',
    'risk_level': 'high',
    'confidence': 0.92,
    'timestamp_ms': 1000,
    'start_ms': 0,
    'end_ms': 2000,
    'bbox': [300, 300, 420, 450],
    'reason': '一个圆形金属卷材放置在黄色安全通道内，占用通行路径。',
    'recommendation': '立即移除通道内物料。',
    'evidence_caption': '通道黄线内放置金属卷材。',
}, 5000)
assert strong['risk_level'] == VideoRiskLevel.high
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'video-worker'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_no_vision_config_falls_back_to_rules():
    code = """
import asyncio
import os
from pathlib import Path

os.environ['VISION_ENABLED'] = 'false'

from aicoding_shared.config import get_settings
from app.main import classify_with_fallback

get_settings.cache_clear()

async def main():
    results, meta = await classify_with_fallback(Path('missing.mp4'), [], 'forklift_overload_sample.mp4', 10000)
    assert meta['analysis_provider'] == 'rule-fallback'
    assert 'vision model is not configured' in meta['fallback_reason']
    assert results[0]['label'] == 'forklift_overload'

asyncio.run(main())
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'video-worker'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_feishu_alert_rules_and_message_are_chinese():
    code = """
import os

os.environ['FEISHU_ALERT_ENABLED'] = 'true'
os.environ['FEISHU_WEBHOOK_URL'] = 'https://example.invalid/feishu'
os.environ['FEISHU_ALERT_RISK_LEVELS'] = 'high,critical,needs_review'

from aicoding_shared.config import get_settings
from aicoding_shared.models import VideoAudit, VideoAuditFinding, VideoRiskLevel
from app.main import _build_feishu_alert_text, _should_send_feishu_alert

get_settings.cache_clear()

high_audit = VideoAudit(
    id=16,
    tenant_id=1,
    file_name='walkway_violation__0_te23.mp4',
    object_key='tenant-1/audits/16/source.mp4',
    risk_level=VideoRiskLevel.high,
    summary='发现 1 个安全风险片段，最高风险等级为高风险。',
)
low_audit = VideoAudit(
    id=17,
    tenant_id=1,
    file_name='safe_walkway.mp4',
    object_key='tenant-1/audits/17/source.mp4',
    risk_level=VideoRiskLevel.low,
)
finding = VideoAuditFinding(
    tenant_id=1,
    audit_id=16,
    label='walkway_violation',
    risk_level=VideoRiskLevel.high,
    confidence=0.92,
    start_ms=7000,
    end_ms=8000,
)

assert _should_send_feishu_alert(high_audit)
assert not _should_send_feishu_alert(low_audit)
message = _build_feishu_alert_text(high_audit, [finding])
assert '安全巡检告警' in message
assert '风险等级：高风险' in message
assert '请安全主管立即打开系统查看证据截图' in message
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'services' / 'video-worker'}{os.pathsep}{ROOT / 'shared'}"
    subprocess.run([sys.executable, "-c", code], check=True, env=env)
