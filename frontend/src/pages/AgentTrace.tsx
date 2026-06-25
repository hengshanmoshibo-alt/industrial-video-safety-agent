import { Button, Card, Descriptions, Space, Table, Tag, Timeline, Typography, message } from "antd";
import { BranchesOutlined, ReloadOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import AuthGate from "../components/AuthGate";
import {
  AgentExplanation,
  getApiErrorMessage,
  getVideoAudit,
  getVideoAuditAgentExplanation,
  listVideoAudits,
  VideoAudit,
  VideoAuditDetail
} from "../services/api";

const stepColor: Record<string, string> = {
  completed: "green",
  running: "blue",
  failed: "red",
  pending: "gray"
};

export default function AgentTrace() {
  const [audits, setAudits] = useState<VideoAudit[]>([]);
  const [selected, setSelected] = useState<VideoAuditDetail>();
  const [explanation, setExplanation] = useState<AgentExplanation>();
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setAudits(await listVideoAudits());
    } catch (error) {
      message.error(`加载 Agent 会话失败：${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  }

  async function openTrace(id: number) {
    try {
      const [detail, explain] = await Promise.all([getVideoAudit(id), getVideoAuditAgentExplanation(id)]);
      setSelected(detail);
      setExplanation(explain);
    } catch (error) {
      message.error(`加载执行轨迹失败：${getApiErrorMessage(error)}`);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>Agent 执行轨迹</h1>
          <p>查看每次巡检 AgentRun 的工具调用、暂停状态和推理解释。</p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </div>

      <Card className="section-card" title={<Space><BranchesOutlined /> Agent 会话</Space>}>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={audits}
          columns={[
            { title: "任务", dataIndex: "id", width: 90, render: (value) => `#${value}` },
            { title: "视频", dataIndex: "file_name", ellipsis: true },
            { title: "状态", dataIndex: "status", width: 110, render: (value) => <Tag>{value}</Tag> },
            { title: "风险", dataIndex: "risk_level", width: 120, render: (value) => <Tag>{value}</Tag> },
            { title: "摘要", dataIndex: "summary", ellipsis: true },
            { title: "操作", width: 100, render: (_, row: VideoAudit) => <Button size="small" onClick={() => openTrace(row.id)}>查看</Button> }
          ]}
        />
      </Card>

      {selected && (
        <Card className="section-card" title={`本次 Agent Run：任务 #${selected.audit.id}`}>
          <Descriptions bordered size="small" column={2}>
            <Descriptions.Item label="Agent状态"><Tag>{selected.agent_run?.status || "-"}</Tag></Descriptions.Item>
            <Descriptions.Item label="当前阶段">{selected.agent_run?.current_stage || selected.agent_run?.current_step || "-"}</Descriptions.Item>
            <Descriptions.Item label="暂停原因" span={2}>{selected.agent_run?.paused_reason || "未暂停"}</Descriptions.Item>
            <Descriptions.Item label="Agent解释" span={2}>{explanation?.why_this_action || "-"}</Descriptions.Item>
          </Descriptions>

          <div className="mt16">
            <Typography.Title level={5}>工具调用轨迹</Typography.Title>
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
                    {String(step.detail?.why || "") && <Typography.Text type="secondary">调用原因：{String(step.detail.why)}</Typography.Text>}
                  </div>
                )
              }))}
            />
          </div>

          <div className="mt16">
            <Typography.Title level={5}>Agent 看到了什么</Typography.Title>
            {(explanation?.what_agent_saw || []).length === 0 ? (
              <Typography.Text type="secondary">暂无结构化视觉记忆。</Typography.Text>
            ) : (
              <div className="audit-report-list">
                {(explanation?.what_agent_saw || []).map((item, index) => (
                  <div className="audit-report-item" key={index}>
                    <Space wrap>
                      <Tag>{String(item.time_range || "-")}</Tag>
                      <Typography.Text strong>{String(item.risk_subject || "关键帧")}</Typography.Text>
                    </Space>
                    <p className="mt8">{String(item.evidence || "")}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      )}
    </AuthGate>
  );
}
