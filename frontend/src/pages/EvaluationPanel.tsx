import { Card, Col, Row, Space, Statistic, Table, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";
import AuthGate from "../components/AuthGate";
import {
  EvaluationMetrics,
  getApiErrorMessage,
  getEvaluationMetrics,
  listSafetyPolicies,
  listSafetyTools,
  SafetyPolicy,
  SafetyTool
} from "../services/api";

function percent(value?: number) {
  return `${Math.round((value || 0) * 100)}%`;
}

export default function EvaluationPanel() {
  const [metrics, setMetrics] = useState<EvaluationMetrics>();
  const [tools, setTools] = useState<SafetyTool[]>([]);
  const [policies, setPolicies] = useState<SafetyPolicy[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [metricData, toolData, policyData] = await Promise.all([
        getEvaluationMetrics(),
        listSafetyTools(),
        listSafetyPolicies()
      ]);
      setMetrics(metricData);
      setTools(toolData);
      setPolicies(policyData);
    } catch (error) {
      message.error(`加载评估面板失败：${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>评估面板</h1>
          <p>跟踪视频处理成功率、bbox 有效率、告警成功率、复核确认率和 Agent 工具能力。</p>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={6}><Card><Statistic title="处理成功率" value={percent(metrics?.processing_success_rate)} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="bbox 有效率" value={percent(metrics?.bbox_valid_rate)} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="飞书告警成功率" value={percent(metrics?.feishu_alert_success_rate)} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="平均耗时(ms)" value={metrics?.avg_processing_ms ?? 0} /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} className="mt16">
        <Col xs={24} md={6}><Card><Statistic title="视频数" value={metrics?.total_videos ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="风险项" value={metrics?.total_findings ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="人工复核" value={metrics?.human_review_count ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="误报率" value={percent(metrics?.false_positive_rate)} /></Card></Col>
      </Row>

      <Card className="section-card" title="Agent Tools">
        <Table
          rowKey="name"
          loading={loading}
          dataSource={tools}
          pagination={false}
          columns={[
            { title: "工具", dataIndex: "name", width: 260, render: (value) => <Typography.Text code>{value}</Typography.Text> },
            { title: "说明", dataIndex: "description" }
          ]}
        />
      </Card>

      <Card className="section-card" title="安全策略">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={policies}
          pagination={false}
          columns={[
            { title: "策略", dataIndex: "title", width: 240 },
            { title: "风险", dataIndex: "severity", width: 100, render: (value) => <Tag>{value}</Tag> },
            {
              title: "动作",
              width: 260,
              render: (_, row: SafetyPolicy) => (
                <Space wrap>
                  {row.auto_alert && <Tag color="blue">自动告警</Tag>}
                  {row.requires_review && <Tag color="purple">需复核</Tag>}
                  {row.recommend_ticket && <Tag color="orange">建议工单</Tag>}
                  {row.requires_verification && <Tag color="green">需复检</Tag>}
                </Space>
              )
            },
            { title: "整改期限", dataIndex: "due_hours", width: 100, render: (value) => `${value}小时` },
            { title: "说明", dataIndex: "description" }
          ]}
        />
      </Card>
    </AuthGate>
  );
}
