import { Button, Card, Col, Row, Statistic, Table, Tag, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import AuthGate from "../components/AuthGate";
import { AnalyticsOverview, getOverview, listConversations, Conversation } from "../services/api";

export default function Dashboard() {
  const [overview, setOverview] = useState<AnalyticsOverview>();
  const [conversations, setConversations] = useState<Conversation[]>([]);

  async function load() {
    try {
      const [o, c] = await Promise.all([getOverview(), listConversations()]);
      setOverview(o);
      setConversations(c.slice(0, 8));
    } catch {
      message.error("加载看板失败，请确认后端已启动并登录");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>运营看板</h1>
          <p>会话、工单、知识库和 AI 自助解决情况。</p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={6}><Card><Statistic title="总会话" value={overview?.conversations ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="待人工" value={overview?.waiting_agent ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="未结工单" value={overview?.tickets_open ?? 0} /></Card></Col>
        <Col xs={24} md={6}><Card><Statistic title="知识文档" value={overview?.knowledge_documents ?? 0} /></Card></Col>
      </Row>
      <Card className="section-card" title="最近会话">
        <Table
          rowKey="id"
          dataSource={conversations}
          pagination={false}
          columns={[
            { title: "访客", dataIndex: "visitor_name" },
            { title: "状态", dataIndex: "status", render: (v) => <Tag>{v}</Tag> },
            { title: "意图", dataIndex: "intent" },
            { title: "优先级", dataIndex: "priority", render: (v) => <Tag color={v === "high" ? "red" : "blue"}>{v}</Tag> }
          ]}
        />
      </Card>
    </AuthGate>
  );
}
