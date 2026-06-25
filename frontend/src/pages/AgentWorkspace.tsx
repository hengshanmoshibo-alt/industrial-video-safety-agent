import { Button, Card, Col, Input, List, Row, Space, Tag, message } from "antd";
import { CheckOutlined, ReloadOutlined, SendOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import AuthGate from "../components/AuthGate";
import {
  acceptConversation,
  agentReply,
  closeConversation,
  Conversation,
  getConversationMessages,
  listConversations,
  Message
} from "../services/api";

export default function AgentWorkspace() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<Conversation>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [reply, setReply] = useState("");

  async function load() {
    const data = await listConversations();
    setConversations(data);
  }

  async function openConversation(item: Conversation) {
    setActive(item);
    setMessages(await getConversationMessages(item.id));
  }

  async function accept() {
    if (!active) return;
    const updated = await acceptConversation(active.id);
    setActive(updated);
    await openConversation(updated);
    await load();
  }

  async function sendReply() {
    if (!active || !reply.trim()) return;
    const msg = await agentReply(active.id, reply);
    setMessages((prev) => [...prev, msg]);
    setReply("");
    message.success("已回复");
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>坐席工作台</h1>
          <p>处理待人工会话，接管后 AI 自动回复会停止。</p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </div>
      <Row gutter={16}>
        <Col xs={24} md={8}>
          <Card title="会话队列">
            <List
              dataSource={conversations}
              renderItem={(item) => (
                <List.Item onClick={() => openConversation(item)} className="clickable">
                  <List.Item.Meta title={item.visitor_name} description={item.intent || "暂无意图"} />
                  <Tag color={item.status === "waiting_agent" ? "red" : "blue"}>{item.status}</Tag>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Card
            title={active ? `会话 #${active.id}` : "选择会话"}
            extra={
              active ? (
                <Space>
                  <Button icon={<CheckOutlined />} onClick={accept}>接管</Button>
                  <Button onClick={() => closeConversation(active.id).then(load)}>关闭</Button>
                </Space>
              ) : null
            }
          >
            <List
              className="agent-messages"
              dataSource={messages}
              locale={{ emptyText: "暂无消息" }}
              renderItem={(item) => (
                <List.Item>
                  <Tag>{item.sender}</Tag>
                  <span>{item.content}</span>
                </List.Item>
              )}
            />
            <Space.Compact className="chat-input">
              <Input value={reply} onChange={(e) => setReply(e.target.value)} onPressEnter={sendReply} placeholder="输入人工回复" />
              <Button type="primary" icon={<SendOutlined />} onClick={sendReply} />
            </Space.Compact>
          </Card>
        </Col>
      </Row>
    </AuthGate>
  );
}
