import { Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography, Upload, message } from "antd";
import { PlusOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import AuthGate from "../components/AuthGate";
import {
  createTicket,
  createTicketVerification,
  listTicketVerifications,
  listTickets,
  Ticket,
  TicketPriority,
  TicketVerification
} from "../services/api";

const statusText: Record<string, string> = {
  open: "待整改",
  pending: "处理中",
  resolved: "已整改",
  closed: "已关闭"
};

const priorityText: Record<string, string> = {
  low: "低",
  normal: "普通",
  high: "高",
  urgent: "紧急"
};

const priorityColor: Record<string, string> = {
  low: "green",
  normal: "blue",
  high: "orange",
  urgent: "red"
};

const verificationText: Record<string, string> = {
  passed: "复检通过",
  failed: "复检未通过",
  needs_review: "需复核"
};

const verificationColor: Record<string, string> = {
  passed: "green",
  failed: "red",
  needs_review: "purple"
};

export default function Tickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [verifications, setVerifications] = useState<Record<number, TicketVerification[]>>({});
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    const items = await listTickets();
    setTickets(items);
    const pairs = await Promise.all(
      items.map(async (item) => [item.id, await listTicketVerifications(item.id).catch(() => [])] as const)
    );
    setVerifications(Object.fromEntries(pairs));
  }

  async function submit() {
    const values = await form.validateFields();
    await createTicket(values);
    setOpen(false);
    form.resetFields();
    await load();
  }

  async function uploadVerification(ticketId: number, file: File) {
    try {
      const result = await createTicketVerification(ticketId, file);
      message.success(`整改后证据已上传：${verificationText[result.status] || result.status}`);
      await load();
    } catch {
      message.error("上传整改后证据失败");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>整改工单</h1>
          <p>跟踪安全巡检告警、人工复核结论和现场整改闭环。</p>
        </div>
        <div>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button className="ml8" type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>新建整改工单</Button>
        </div>
      </div>
      <Card>
        <Table
          rowKey="id"
          dataSource={tickets}
          columns={[
            { title: "整改事项", dataIndex: "title", width: 260 },
            { title: "状态", dataIndex: "status", width: 110, render: (v) => <Tag>{statusText[v] || v}</Tag> },
            { title: "优先级", dataIndex: "priority", width: 100, render: (v) => <Tag color={priorityColor[v] || "blue"}>{priorityText[v] || v}</Tag> },
            {
              title: "处理说明",
              dataIndex: "description",
              render: (v) => <pre className="ticket-description">{v}</pre>
            },
            {
              title: "整改后证据",
              width: 180,
              render: (_, row: Ticket) => {
                const latest = verifications[row.id]?.[0];
                return (
                  <Space direction="vertical" size={6}>
                    {latest ? <Tag color={verificationColor[latest.status]}>{verificationText[latest.status] || latest.status}</Tag> : <Tag>未复检</Tag>}
                    <Upload
                      showUploadList={false}
                      accept="image/*,video/*"
                      beforeUpload={(file) => {
                        uploadVerification(row.id, file as File);
                        return false;
                      }}
                    >
                      <Button size="small" icon={<UploadOutlined />}>上传整改后证据</Button>
                    </Upload>
                  </Space>
                );
              }
            }
          ]}
          expandable={{
            expandedRowRender: (row: Ticket) => (
              <div className="ticket-verification-panel">
                <Typography.Title level={5}>整改后证据记录</Typography.Title>
                {(verifications[row.id] || []).length === 0 ? (
                  <Typography.Text type="secondary">暂无复检证据。</Typography.Text>
                ) : (
                  <Space direction="vertical" className="full-width">
                    {(verifications[row.id] || []).map((item) => (
                      <Card size="small" key={item.id}>
                        <Space wrap>
                          <Tag color={verificationColor[item.status]}>{verificationText[item.status] || item.status}</Tag>
                          <Typography.Text type="secondary">{new Date(item.created_at).toLocaleString()}</Typography.Text>
                          <Typography.Text type="secondary">{item.content_type}</Typography.Text>
                        </Space>
                        <Typography.Paragraph className="mt8">{item.summary}</Typography.Paragraph>
                      </Card>
                    ))}
                  </Space>
                )}
              </div>
            )
          }}
        />
      </Card>
      <Modal title="新建整改工单" open={open} onCancel={() => setOpen(false)} onOk={submit}>
        <Form form={form} layout="vertical" initialValues={{ priority: "normal" satisfies TicketPriority }}>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="priority" label="优先级"><Select options={["low", "normal", "high", "urgent"].map((v) => ({ value: v, label: v }))} /></Form.Item>
          <Form.Item name="description" label="说明" rules={[{ required: true }]}><Input.TextArea rows={6} /></Form.Item>
        </Form>
      </Modal>
    </AuthGate>
  );
}
