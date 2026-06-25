import { Button, Card, Input, List, Space, Tag, message } from "antd";
import { CustomerServiceOutlined, SendOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { createChatSession, handoff, Message, sendChatMessage } from "../services/api";

export default function ChatWidget() {
  const [conversationId, setConversationId] = useState<number>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    createChatSession().then((session) => setConversationId(session.id));
  }, []);

  async function send() {
    if (!conversationId || !content.trim()) return;
    setLoading(true);
    try {
      const result = await sendChatMessage(conversationId, content);
      setMessages((prev) => [...prev, ...result]);
      setContent("");
    } catch {
      message.error("发送失败");
    } finally {
      setLoading(false);
    }
  }

  async function requestHandoff() {
    if (!conversationId) return;
    await handoff(conversationId);
    message.success("已请求转人工");
  }

  return (
    <div className="chat-layout">
      <Card className="chat-panel" title={<Space><CustomerServiceOutlined /> 网页客服窗口</Space>}>
        <List
          className="message-list"
          dataSource={messages}
          locale={{ emptyText: "请输入一个电商客服问题，例如：我想退款多久到账？" }}
          renderItem={(item) => (
            <List.Item className={`message-row ${item.sender}`}>
              <div className="message-bubble">
                <div className="message-meta">
                  <Tag>{item.sender}</Tag>
                  {item.confidence > 0 ? <span>置信度 {(item.confidence * 100).toFixed(0)}%</span> : null}
                </div>
                <div>{item.content}</div>
                {item.sources?.length ? <small>来源：{String(item.sources[0].title)}</small> : null}
              </div>
            </List.Item>
          )}
        />
        <Space.Compact className="chat-input">
          <Input
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onPressEnter={send}
            placeholder="输入访客问题"
          />
          <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={send} />
        </Space.Compact>
        <Button className="handoff-btn" onClick={requestHandoff}>转人工</Button>
      </Card>
    </div>
  );
}
