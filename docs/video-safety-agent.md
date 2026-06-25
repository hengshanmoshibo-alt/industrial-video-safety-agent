# 工业/仓储安全巡检视频 Agent

## 定位

该模块把 AiCoding 从智能客服平台扩展为企业安全巡检与整改闭环平台。用户上传工业、仓储、门店后场巡检视频后，系统自动抽取关键帧，优先调用多模态视觉大模型识别安全风险，生成风险时间轴、证据截图、整改建议，并支持一键创建整改工单。

核心闭环：

```text
视频上传 -> Redis 异步任务 -> FFmpeg 抽关键帧 -> Vision LLM 识别 -> 风险分级 -> 证据截图 -> 整改报告 -> 工单派发 -> 复核归档
```

识别优先级：

```text
多模态视觉大模型 -> 本地 R3D-18 备用模型 -> 规则降级
```

因此第一版不再强制要求 `models/safety_r3d18.pt`。只要配置 OpenAI-compatible 视觉模型，就可以走多模态识别主路径；没有视觉模型时仍可用 fallback 跑通 Demo。

## 架构

- `video-audit-service`：视频上传、任务查询、报告查询、证据图片访问、整改工单创建。
- `video-worker`：Redis 队列消费者，负责 FFmpeg 抽帧、Vision LLM 调用、fallback、本地证据截图保存、报告生成。
- `api-gateway`：代理 `/api/video-audits`。
- `frontend`：提供“安全巡检”页面，展示分析来源、模型、风险时间轴和证据截图。
- `PostgreSQL`：保存审核任务、风险事件、证据元数据和结构化报告。
- `MinIO`：保存原始视频和证据截图；本地开发可通过 `STORAGE_BACKEND=local` 使用文件系统。

## 配置

视觉模型配置：

```env
VISION_ENABLED=true
VISION_BASE_URL=
VISION_API_KEY=
VISION_MODEL=
VISION_FRAME_BATCH_SIZE=4
VISION_MAX_FRAMES=24
VISION_TIMEOUT_SECONDS=60
```

如果 `VISION_BASE_URL`、`VISION_API_KEY` 或 `VISION_MODEL` 为空，会分别回退到 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。

飞书告警配置：

```env
FEISHU_ALERT_ENABLED=false
FEISHU_WEBHOOK_URL=
FEISHU_WEBHOOK_SECRET=
FEISHU_ALERT_RISK_LEVELS=high,critical,needs_review
FEISHU_ALERT_TIMEOUT_SECONDS=10
```

配置飞书自定义机器人 Webhook 后，`video-worker` 会在视频分析完成时自动判断风险等级。命中 `FEISHU_ALERT_RISK_LEVELS` 的任务会立即向飞书群发送中文安全告警，并在 `AuditLog` 中记录 `video_audit.feishu_alert_sent`；发送失败不会阻断视频分析流程，会记录 `video_audit.feishu_alert_failed` 供排查。

## 任务状态与权限

- 任务状态：`queued`、`processing`、`completed`、`needs_review`、`failed`。
- 风险等级：`low`、`medium`、`high`、`critical`、`needs_review`。
- `admin`、`supervisor`、`auditor` 可查看租户内全部巡检任务。
- `agent` 只能查看自己上传或分配给自己的巡检任务。
- `admin`、`supervisor`、`agent` 可以从巡检结果创建整改工单。

## 风险识别范围

固定 8 类行为：

- 安全类：`safe_walkway`、`authorized_intervention`、`closed_panel_cover`、`safe_carrying`
- 风险类：`walkway_violation`、`unauthorized_intervention`、`opened_panel_cover`、`forklift_overload`

风险等级规则：

- `critical`：`forklift_overload`
- `high`：`walkway_violation`、`unauthorized_intervention`、`opened_panel_cover`
- `needs_review`：视觉模型不确定、画面模糊、未知 label、置信度低于 `VIDEO_AUDIT_CONFIDENCE_THRESHOLD`
- `low`：未发现明确风险

视觉模型必须返回严格 JSON。系统会校验 label、risk level、置信度和时间戳；非法输出会转为 `needs_review` 或触发 fallback。

## API

- `POST /api/video-audits`：上传视频并创建审核任务。
- `GET /api/video-audits`：查询审核任务列表。
- `GET /api/video-audits/{id}`：查询任务详情、风险发现、证据和报告。
- `GET /api/video-audits/{id}/report`：查询结构化报告。
- `GET /api/video-audits/{id}/evidence/{evidence_id}/image`：读取证据截图。
- `POST /api/video-audits/{id}/tickets`：创建整改工单。
- `GET /api/video-audits/metrics/overview`：查询巡检统计。

## 报告字段

`VideoAuditReport.report` 包含：

- `analysis_provider`：`vision-llm`、`local-r3d18` 或 `rule-fallback`
- `analysis_model`
- `frames_analyzed`
- `vision_raw_outputs`
- `fallback_reason`
- `findings`
- `recommend_ticket`
- `review_notice`

## 公开数据与备用训练

公开数据集：

- Hugging Face：`Voxel51/Safe_and_Unsafe_Behaviours`
- Mendeley：`Safe and Unsafe Behaviours Dataset`

R3D-18 训练脚本保留为备用能力：

```bash
python scripts/download_safety_dataset.py
python scripts/train_safety_classifier.py --data-dir data/safe_unsafe_behaviours --output models/safety_r3d18.pt --epochs 3 --batch-size 2
```

## 运行与验收

启动：

```bash
docker compose up --build
```

访问：

```text
http://localhost:5173
admin / Admin123!
```

验证命令：

```bash
pytest -q
npm run build
docker compose config --quiet
python scripts/evaluate_safety_agent.py --mode api --max-samples 24
```

## 简历表述

设计并实现多模态大模型驱动的工业/仓储安全巡检视频 Agent，支持巡检视频上传、FFmpeg 抽关键帧、Vision LLM 风险识别、风险时间轴定位、证据截图生成和整改工单闭环。系统基于 FastAPI 微服务、Redis 队列、MinIO 对象存储、PostgreSQL 和 React 管理台构建，并提供本地 R3D-18 模型与规则降级能力，实现从视频证据到企业安全整改流程的自动化。
