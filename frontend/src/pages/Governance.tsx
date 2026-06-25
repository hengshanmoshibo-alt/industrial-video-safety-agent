import { Button, Card, Col, Descriptions, Row, Space, Table, Tag, message } from "antd";
import { ApiOutlined, CloudServerOutlined, ExperimentOutlined, ReloadOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import AuthGate from "../components/AuthGate";
import {
  Channel,
  getSystemHealth,
  listChannels,
  listKnowledgeVersions,
  listModelCallLogs,
  listModelProviders,
  listPromptVersions,
  listQualityRules,
  listTenants,
  ModelCallLog,
  ModelProvider,
  runQualityReports,
  simulateWebhook,
  Tenant
} from "../services/api";

export default function Governance() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [logs, setLogs] = useState<ModelCallLog[]>([]);
  const [prompts, setPrompts] = useState<Array<Record<string, unknown>>>([]);
  const [versions, setVersions] = useState<Array<Record<string, unknown>>>([]);
  const [rules, setRules] = useState<Array<Record<string, unknown>>>([]);
  const [health, setHealth] = useState<Record<string, string>>({});

  async function load() {
    try {
      const [t, c, p, l, pv, kv, qr, h] = await Promise.all([
        listTenants(),
        listChannels(),
        listModelProviders(),
        listModelCallLogs(),
        listPromptVersions(),
        listKnowledgeVersions(),
        listQualityRules(),
        getSystemHealth()
      ]);
      setTenants(t);
      setChannels(c);
      setProviders(p);
      setLogs(l);
      setPrompts(pv);
      setVersions(kv);
      setRules(qr);
      setHealth(h);
    } catch {
      message.error("加载治理数据失败，请确认已登录且网关正常");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>终极版治理中心</h1>
          <p>租户、渠道、模型、知识、质检和系统健康的统一治理视图。</p>
        </div>
        <Space>
          <Button
            icon={<SafetyCertificateOutlined />}
            onClick={() => runQualityReports().then(() => {
              message.success("质检任务已完成");
              load();
            })}
          >
            运行质检
          </Button>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card title={<Space><CloudServerOutlined /> 系统健康</Space>}>
            <Descriptions column={1} size="small">
              {Object.entries(health).map(([key, value]) => (
                <Descriptions.Item key={key} label={key}>
                  <Tag color={value === "ok" ? "green" : value === "degraded" ? "orange" : "blue"}>{value}</Tag>
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title={<Space><SafetyCertificateOutlined /> 租户</Space>}>
            <Table rowKey="id" dataSource={tenants} pagination={false} size="small" columns={[
              { title: "标识", dataIndex: "slug" },
              { title: "名称", dataIndex: "name" },
              { title: "套餐", dataIndex: "plan" }
            ]} />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title={<Space><ApiOutlined /> 渠道适配</Space>}>
            <Table rowKey="id" dataSource={channels} pagination={false} size="small" columns={[
              { title: "名称", dataIndex: "name" },
              { title: "类型", dataIndex: "type", render: (v) => <Tag>{v}</Tag> },
              {
                title: "模拟",
                render: (_, row: Channel) => <Button size="small" onClick={() => simulateWebhook(row.id, "我想退款").then(() => message.success("模拟回调已生成"))}>回调</Button>
              }
            ]} />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title={<Space><ExperimentOutlined /> 模型治理</Space>}>
            <Table rowKey="id" dataSource={providers} pagination={false} size="small" columns={[
              { title: "供应商", dataIndex: "name" },
              { title: "类型", dataIndex: "provider_type" },
              { title: "模型", dataIndex: "model" }
            ]} />
          </Card>
        </Col>
      </Row>

      <Card className="section-card" title="提示词版本">
        <Table rowKey={(row) => String(row.id)} dataSource={prompts} size="small" columns={[
          { title: "ID", dataIndex: "id" },
          { title: "版本", dataIndex: "version" },
          { title: "内容", dataIndex: "content" }
        ]} />
      </Card>
      <Card className="section-card" title="知识版本与审批">
        <Table rowKey={(row) => String(row.id)} dataSource={versions} size="small" columns={[
          { title: "文档", dataIndex: "document_id" },
          { title: "版本", dataIndex: "version" },
          { title: "状态", dataIndex: "status", render: (v) => <Tag>{String(v)}</Tag> }
        ]} />
      </Card>
      <Card className="section-card" title="质检规则">
        <Table rowKey={(row) => String(row.id)} dataSource={rules} size="small" columns={[
          { title: "名称", dataIndex: "name" },
          { title: "类型", dataIndex: "rule_type" },
          { title: "启用", dataIndex: "enabled", render: (v) => <Tag color={v ? "green" : "default"}>{v ? "启用" : "停用"}</Tag> }
        ]} />
      </Card>
      <Card className="section-card" title="模型调用日志">
        <Table rowKey="id" dataSource={logs} size="small" columns={[
          { title: "供应商", dataIndex: "provider" },
          { title: "模型", dataIndex: "model" },
          { title: "提示词", dataIndex: "prompt_version" },
          { title: "耗时", dataIndex: "latency_ms", render: (v) => `${v} ms` },
          { title: "输入摘要", dataIndex: "input_summary" }
        ]} />
      </Card>
    </AuthGate>
  );
}
