import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Image,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Timeline,
  Typography,
  Upload,
  message
} from "antd";
import { BellOutlined, BranchesOutlined, FileDoneOutlined, ReloadOutlined, SafetyCertificateOutlined, UploadOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import AuthGate from "../components/AuthGate";
import {
  createVideoAudit,
  createVideoAuditTicket,
  getAgentOverviewMetrics,
  getApiErrorMessage,
  getEvidenceImage,
  getVideoAudit,
  getVideoAuditMetrics,
  listVideoAudits,
  reviewVideoAudit,
  resumeVideoAudit,
  AgentOverviewMetrics,
  VideoAudit,
  VideoAuditDetail,
  VideoAuditEvidence,
  VideoAuditFinding,
  VideoAuditMetrics,
  VideoRiskLevel
} from "../services/api";

const riskColor: Record<VideoRiskLevel, string> = {
  low: "green",
  medium: "gold",
  high: "orange",
  critical: "red",
  needs_review: "purple"
};

const riskText: Record<VideoRiskLevel, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  critical: "严重风险",
  needs_review: "需人工复核"
};

const statusText: Record<string, string> = {
  queued: "排队中",
  processing: "分析中",
  completed: "已完成",
  needs_review: "需复核",
  failed: "失败"
};

const stepColor: Record<string, string> = {
  completed: "green",
  running: "blue",
  failed: "red",
  pending: "gray"
};

const reviewDecisionText: Record<string, string> = {
  confirmed_violation: "确认为违规",
  false_positive: "判定为误报",
  needs_more_evidence: "需要补充证据"
};

const providerText: Record<string, string> = {
  "vision-llm": "视觉大模型",
  "local-r3d18": "本地分类模型",
  "rule-fallback": "规则兜底"
};

const labelText: Record<string, string> = {
  safe_walkway: "人员在安全通道内通行",
  authorized_intervention: "授权人员按流程操作设备",
  closed_panel_cover: "设备护罩/柜门保持关闭",
  safe_carrying: "物料搬运方式安全",
  walkway_violation: "人员进入非安全通道或危险区域",
  unauthorized_intervention: "疑似未授权干预设备",
  opened_panel_cover: "设备护罩/柜门处于打开状态",
  forklift_overload: "叉车或搬运设备疑似超载"
};

function seconds(ms: number) {
  return `${Math.round(ms / 1000)}s`;
}

function cleanReportText(value: unknown) {
  return String(value || "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/\*\*/g, "")
    .replace(/#{1,6}\s*/g, "")
    .replace(/^\s*[>|-]\s*/gm, "")
    .replace(/\|[-:\s|]+\|/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function isNoisyMarkdown(value: unknown) {
  const text = String(value || "");
  return /(\|.*\|)|#{2,}|\*\*/.test(text);
}

export default function SafetyInspection() {
  const [audits, setAudits] = useState<VideoAudit[]>([]);
  const [metrics, setMetrics] = useState<VideoAuditMetrics>();
  const [agentMetrics, setAgentMetrics] = useState<AgentOverviewMetrics>();
  const [selected, setSelected] = useState<VideoAuditDetail>();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [imageUrls, setImageUrls] = useState<Record<number, string>>({});

  async function load() {
    setLoading(true);
    try {
      const [items, overview, agentOverview] = await Promise.all([listVideoAudits(), getVideoAuditMetrics(), getAgentOverviewMetrics()]);
      setAudits(items);
      setMetrics(overview);
      setAgentMetrics(agentOverview);
    } catch {
      message.error("加载安全巡检数据失败，请确认已登录且视频审核服务正常");
    } finally {
      setLoading(false);
    }
  }

  async function openDetail(id: number) {
    try {
      const detail = await getVideoAudit(id);
      setSelected(detail);
      setDrawerOpen(true);
      const pairs = await Promise.all(
        detail.evidences.slice(0, 6).map(async (item) => [item.id, await getEvidenceImage(id, item.id)] as const)
      );
      setImageUrls(Object.fromEntries(pairs));
    } catch {
      message.error("加载审核详情失败");
    }
  }

  async function upload(file: File) {
    if (file.size > 1024 * 1024 * 1024) {
      message.error("上传失败：视频文件不能超过 1GB");
      return;
    }
    try {
      await createVideoAudit(file);
      message.success("视频已上传，审核任务已进入队列");
      load();
    } catch (error) {
      message.error(`上传失败：${getApiErrorMessage(error, "请确认文件格式和服务状态")}`);
    }
  }

  async function createTicket() {
    if (!selected) return;
    try {
      const result = await createVideoAuditTicket(selected.audit.id);
      message.success(`整改工单已创建：#${result.ticket_id}`);
      await load();
      await openDetail(selected.audit.id);
    } catch {
      message.error("创建整改工单失败");
    }
  }

  async function submitReview(decision: "confirmed_violation" | "false_positive" | "needs_more_evidence") {
    if (!selected) return;
    try {
      await reviewVideoAudit(selected.audit.id, {
        decision,
        comment: reviewDecisionText[decision]
      });
      await resumeVideoAudit(selected.audit.id);
      message.success("人工复核结论已保存，Agent 已恢复执行");
      await openDetail(selected.audit.id);
      await load();
    } catch (error) {
      message.error(`提交复核失败：${getApiErrorMessage(error)}`);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 10000);
    return () => window.clearInterval(timer);
  }, []);

  const reportSupplement = useMemo(() => {
    const report = selected?.report?.report;
    if (!report) return "";
    const raw = report.llm_report || "";
    if (!raw || isNoisyMarkdown(raw)) return "";
    const cleaned = cleanReportText(raw);
    return cleaned.length > 500 ? `${cleaned.slice(0, 500)}...` : cleaned;
  }, [selected]);
  const recommendations = useMemo(() => {
    if (!selected) return [];
    return Array.from(new Set(selected.findings.map((item) => item.recommendation).filter(Boolean)));
  }, [selected]);
  const reportMeta = selected?.report?.report;
  const analysisProvider = String(reportMeta?.analysis_provider || "-");
  const analysisModel = String(reportMeta?.analysis_model || selected?.report?.model_version || "-");
  const fallbackReason = String(reportMeta?.fallback_reason || "");

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>安全巡检</h1>
          <p>上传工业/仓储巡检视频，自动识别不安全行为、生成证据链和整改工单。</p>
        </div>
        <Space>
          <Upload
            accept="video/*"
            showUploadList={false}
            beforeUpload={(file) => {
              upload(file as File);
              return false;
            }}
          >
            <Button type="primary" icon={<UploadOutlined />}>上传视频</Button>
          </Upload>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={5}><Card><Statistic title="总审核数" value={metrics?.total ?? 0} /></Card></Col>
        <Col xs={24} md={5}><Card><Statistic title="已完成" value={metrics?.completed ?? 0} /></Card></Col>
        <Col xs={24} md={5}><Card><Statistic title="高风险告警" value={metrics?.high_risk ?? 0} valueStyle={{ color: "#cf1322" }} /></Card></Col>
        <Col xs={24} md={5}><Card><Statistic title="需人工复核" value={metrics?.needs_review ?? 0} valueStyle={{ color: "#722ed1" }} /></Card></Col>
        <Col xs={24} md={4}><Card><Statistic title="已派工单" value={metrics?.tickets_created ?? 0} /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} className="mt16">
        <Col xs={24} md={6}><Card><Statistic title="Agent运行" value={agentMetrics?.agent_runs ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="执行成功" value={agentMetrics?.completed_runs ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="飞书告警" value={agentMetrics?.sent_alerts ?? 0} valueStyle={{ color: "#1677ff" }} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="平均耗时(ms)" value={agentMetrics?.avg_processing_ms ?? 0} /></Card></Col>
      </Row>

      <Alert
        className="section-card"
        type="info"
        showIcon
        message="告警与复核分离"
        description="明确违规会进入高风险告警；证据不足但值得关注的画面会进入人工复核，不直接作为违规结论。"
      />

      <Card className="section-card" title={<Space><SafetyCertificateOutlined /> 巡检任务</Space>}>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={audits}
          columns={[
            { title: "文件", dataIndex: "file_name", ellipsis: true },
            { title: "状态", dataIndex: "status", render: (value) => <Tag>{statusText[value] || value}</Tag> },
            { title: "风险", dataIndex: "risk_level", render: (value: VideoRiskLevel) => <Tag color={riskColor[value]}>{riskText[value]}</Tag> },
            { title: "摘要", dataIndex: "summary", ellipsis: true },
            { title: "工单", dataIndex: "created_ticket_id", render: (value) => value ? <Tag color="blue">#{value}</Tag> : <Tag>未创建</Tag> },
            { title: "创建时间", dataIndex: "created_at", render: (value) => new Date(value).toLocaleString() },
            { title: "操作", render: (_, row: VideoAudit) => <Button size="small" onClick={() => openDetail(row.id)}>查看</Button> }
          ]}
        />
      </Card>

      <Drawer
        title={selected ? `安全巡检详情 #${selected.audit.id}` : "安全巡检详情"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={860}
      >
        {selected && (
          <Space direction="vertical" size={16} className="full-width">
            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label="文件">{selected.audit.file_name}</Descriptions.Item>
              <Descriptions.Item label="状态"><Tag>{statusText[selected.audit.status] || selected.audit.status}</Tag></Descriptions.Item>
              <Descriptions.Item label="风险"><Tag color={riskColor[selected.audit.risk_level]}>{riskText[selected.audit.risk_level]}</Tag></Descriptions.Item>
              <Descriptions.Item label="时长">{seconds(selected.audit.duration_ms)}</Descriptions.Item>
              <Descriptions.Item label="分析来源"><Tag>{providerText[analysisProvider] || analysisProvider}</Tag></Descriptions.Item>
              <Descriptions.Item label="分析模型">{analysisModel}</Descriptions.Item>
              <Descriptions.Item label="摘要" span={2}>{selected.audit.summary || selected.audit.error || "-"}</Descriptions.Item>
            </Descriptions>

            {(selected.audit.status === "needs_review" || selected.audit.risk_level === "needs_review") && (
              <Alert
                type="warning"
                showIcon
                message="需要人工复核"
                description={fallbackReason || "模型置信度不足、画面质量不足或证据不明确，请安全主管结合原视频复核。"}
              />
            )}

            <Space>
              <Button
                icon={<FileDoneOutlined />}
                disabled={Boolean(selected.audit.created_ticket_id)}
                onClick={createTicket}
              >
                {selected.audit.created_ticket_id ? `已创建工单 #${selected.audit.created_ticket_id}` : "创建整改工单"}
              </Button>
            </Space>

            <Card title={<Space><BranchesOutlined /> Agent 决策</Space>} size="small">
              <Descriptions bordered size="small" column={2}>
                <Descriptions.Item label="Agent状态">
                  <Tag>{selected.agent_run?.status || "-"}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="当前阶段">
                  {selected.agent_run?.current_stage || selected.agent_run?.current_step || "-"}
                </Descriptions.Item>
                <Descriptions.Item label="是否告警">
                  <Tag color={selected.agent_decision?.send_feishu_alert ? "blue" : "default"}>
                    {selected.agent_decision?.send_feishu_alert ? "自动告警" : "不告警"}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="工单建议">
                  <Tag color={selected.agent_decision?.recommend_ticket ? "orange" : "default"}>
                    {selected.agent_decision?.recommend_ticket ? "建议创建" : "不建议"}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="人工复核">
                  <Tag color={selected.agent_decision?.needs_human_review ? "purple" : "green"}>
                    {selected.agent_decision?.needs_human_review ? "需要复核" : "无需复核"}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="复检要求">
                  <Tag color={selected.agent_decision?.requires_verification ? "blue" : "default"}>
                    {selected.agent_decision?.requires_verification ? "需要复检" : "无需复检"}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="整改期限" span={2}>
                  {String(selected.agent_decision?.recommended_due_hours ?? "-")} 小时
                </Descriptions.Item>
                <Descriptions.Item label="决策原因" span={2}>
                  {String(selected.agent_decision?.decision_reason || "-")}
                </Descriptions.Item>
                {selected.agent_run?.paused_reason && (
                  <Descriptions.Item label="暂停原因" span={2}>
                    {selected.agent_run.paused_reason}
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>

            <Card title="Agent 执行轨迹" size="small">
              {(selected.agent_steps || []).length === 0 ? (
                <Alert type="info" showIcon message="暂无 Agent 执行轨迹" />
              ) : (
                <Timeline
                  items={(selected.agent_steps || []).map((step) => ({
                    color: stepColor[step.status] || "blue",
                    children: (
                      <div>
                        <Space wrap>
                          <Tag color={stepColor[step.status] || "blue"}>{step.status}</Tag>
                          <Typography.Text strong>{step.step_order}. {step.tool_name}</Typography.Text>
                          <Typography.Text type="secondary">{step.latency_ms} ms</Typography.Text>
                        </Space>
                        <p className="mt8">{step.output_summary || step.input_summary}</p>
                        {step.error && <Typography.Text type="danger">{step.error}</Typography.Text>}
                      </div>
                    )
                  }))}
                />
              )}
            </Card>

            <Card title="视频记忆" size="small">
              {(selected.memory_segments || []).length === 0 ? (
                <Alert type="info" showIcon message="暂无视频记忆片段" />
              ) : (
                <Timeline
                  items={(selected.memory_segments || []).map((segment) => ({
                    color: "blue",
                    children: (
                      <div>
                        <Space wrap>
                          <Typography.Text strong>{seconds(segment.start_ms)} - {seconds(segment.end_ms)}</Typography.Text>
                          <Tag>{segment.risk_subject || "风险主体"}</Tag>
                          {segment.bbox && <Typography.Text type="secondary">bbox [{segment.bbox.join(", ")}]</Typography.Text>}
                        </Space>
                        <p className="mt8">{segment.evidence}</p>
                      </div>
                    )
                  }))}
                />
              )}
            </Card>

            <Card title="策略依据与告警" size="small">
              <Row gutter={[12, 12]}>
                <Col xs={24} md={12}>
                  <Typography.Title level={5}>安全策略</Typography.Title>
                  {(selected.matched_rules || []).length === 0 ? (
                    <Typography.Text type="secondary">暂无匹配策略。</Typography.Text>
                  ) : (
                    <div className="audit-report-list">
                      {(selected.matched_rules || []).map((rule) => (
                        <div className="audit-report-item" key={rule.id}>
                          <Space wrap>
                            <Tag color={riskColor[rule.severity]}>{riskText[rule.severity]}</Tag>
                            <Typography.Text strong>{rule.title}</Typography.Text>
                            <Typography.Text type="secondary">{rule.due_hours}小时</Typography.Text>
                          </Space>
                          <Typography.Paragraph className="mt8">{rule.description}</Typography.Paragraph>
                        </div>
                      ))}
                    </div>
                  )}
                </Col>
                <Col xs={24} md={12}>
                  <Typography.Title level={5}><BellOutlined /> 飞书告警</Typography.Title>
                  {(selected.alert_events || []).length === 0 ? (
                    <Typography.Text type="secondary">暂无告警记录。</Typography.Text>
                  ) : (
                    <div className="audit-report-list">
                      {(selected.alert_events || []).map((event) => (
                        <div className="audit-report-item" key={event.id}>
                          <Space wrap>
                            <Tag color={event.status === "sent" ? "blue" : "red"}>{event.status}</Tag>
                            <Typography.Text>{event.channel}</Typography.Text>
                            <Typography.Text type="secondary">{new Date(event.created_at).toLocaleString()}</Typography.Text>
                          </Space>
                          {event.error && <Typography.Paragraph type="danger">{event.error}</Typography.Paragraph>}
                        </div>
                      ))}
                    </div>
                  )}
                </Col>
              </Row>
            </Card>

            <Card title="人工复核" size="small">
              <Space wrap className="mb8">
                <Button onClick={() => submitReview("confirmed_violation")}>确认为违规</Button>
                <Button onClick={() => submitReview("false_positive")}>判定为误报</Button>
                <Button onClick={() => submitReview("needs_more_evidence")}>需要补充证据</Button>
              </Space>
              {(selected.reviews || []).length === 0 ? (
                <Typography.Text type="secondary">暂无人工复核记录。</Typography.Text>
              ) : (
                <Timeline
                  items={(selected.reviews || []).map((review) => ({
                    color: review.decision === "false_positive" ? "green" : review.decision === "needs_more_evidence" ? "purple" : "orange",
                    children: (
                      <div>
                        <Space wrap>
                          <Tag>{reviewDecisionText[review.decision]}</Tag>
                          <Typography.Text type="secondary">{new Date(review.created_at).toLocaleString()}</Typography.Text>
                        </Space>
                        {review.comment && <p className="mt8">{review.comment}</p>}
                      </div>
                    )
                  }))}
                />
              )}
            </Card>

            <Card title="风险时间轴" size="small">
              {selected.findings.length === 0 ? (
                <Alert type="success" showIcon message="未发现明确风险片段" />
              ) : (
                <Timeline
                  items={selected.findings.map((finding: VideoAuditFinding) => ({
                    color: riskColor[finding.risk_level],
                    children: (
                      <div>
                        <Space wrap>
                          <Tag color={riskColor[finding.risk_level]}>{riskText[finding.risk_level]}</Tag>
                          <Typography.Text strong>{labelText[finding.label] || finding.label}</Typography.Text>
                          <Typography.Text type="secondary">{seconds(finding.start_ms)} - {seconds(finding.end_ms)}</Typography.Text>
                          <Typography.Text type="secondary">置信度 {Math.round(finding.confidence * 100)}%</Typography.Text>
                        </Space>
                        <p className="mt8">{finding.reason}</p>
                        <Typography.Text>{finding.recommendation}</Typography.Text>
                      </div>
                    )
                  }))}
                />
              )}
            </Card>

            <Card title="证据截图" size="small">
              <Row gutter={[12, 12]}>
                {selected.evidences.map((item: VideoAuditEvidence) => (
                  <Col xs={24} md={12} key={item.id}>
                    <Card size="small">
                      {imageUrls[item.id] && <Image src={imageUrls[item.id]} alt={item.caption} />}
                      <p className="mt8">{seconds(item.timestamp_ms)} · {item.caption}</p>
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>

            <Card title="审核报告" size="small">
              <div className="audit-report">
                <section>
                  <Typography.Title level={5}>总体结论</Typography.Title>
                  <Space wrap className="mb8">
                    <Tag color={riskColor[selected.audit.risk_level]}>{riskText[selected.audit.risk_level]}</Tag>
                    <Typography.Text type="secondary">任务 #{selected.audit.id}</Typography.Text>
                    <Typography.Text type="secondary">{providerText[analysisProvider] || analysisProvider} / {analysisModel}</Typography.Text>
                  </Space>
                  <Typography.Paragraph>{selected.audit.summary || "本次巡检暂无明确结论。"}</Typography.Paragraph>
                </section>

                <section>
                  <Typography.Title level={5}>关键风险</Typography.Title>
                  {selected.findings.length === 0 ? (
                    <Alert type="success" showIcon message="未发现明确不安全行为" />
                  ) : (
                    <div className="audit-report-list">
                      {selected.findings.map((finding) => (
                        <div className="audit-report-item" key={finding.id}>
                          <Space wrap>
                            <Tag color={riskColor[finding.risk_level]}>{riskText[finding.risk_level]}</Tag>
                            <Typography.Text strong>{labelText[finding.label] || finding.label}</Typography.Text>
                            <Typography.Text type="secondary">{seconds(finding.start_ms)} - {seconds(finding.end_ms)}</Typography.Text>
                            <Typography.Text type="secondary">置信度 {Math.round(finding.confidence * 100)}%</Typography.Text>
                          </Space>
                          <Typography.Paragraph className="mt8">{finding.reason}</Typography.Paragraph>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                <section>
                  <Typography.Title level={5}>整改建议</Typography.Title>
                  {recommendations.length > 0 ? (
                    <ol className="audit-report-steps">
                      {recommendations.map((item) => <li key={item}>{item}</li>)}
                    </ol>
                  ) : (
                    <Typography.Paragraph>维持现场通道、设备防护和物料摆放巡检，暂不需要创建整改项。</Typography.Paragraph>
                  )}
                </section>

                <section>
                  <Typography.Title level={5}>复核要求</Typography.Title>
                  <ul className="audit-report-steps">
                    <li>安全主管结合原视频、证据截图和现场情况复核模型结论。</li>
                    <li>高风险、严重风险和需复核结果确认后，应派发整改工单并跟踪闭环。</li>
                    <li>整改完成后复拍或复检，保留证据用于归档。</li>
                  </ul>
                </section>

                {reportSupplement && (
                  <section>
                    <Typography.Title level={5}>模型补充</Typography.Title>
                    <Typography.Paragraph className="audit-report-supplement">{reportSupplement}</Typography.Paragraph>
                  </section>
                )}
              </div>
              {selected.report && (
                <Typography.Text type="secondary">
                  模型版本：{selected.report.model_version}，处理耗时：{selected.report.processing_ms} ms
                </Typography.Text>
              )}
            </Card>
          </Space>
        )}
      </Drawer>
    </AuthGate>
  );
}
