import { Button, Card, Form, Input, Modal, Space, Table, Tag, message } from "antd";
import { DatabaseOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import AuthGate from "../components/AuthGate";
import { createDocument, KnowledgeDocument, listDocuments, seedEcommerceKb } from "../services/api";

export default function KnowledgeBase() {
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    setDocs(await listDocuments());
  }

  async function submit() {
    const values = await form.validateFields();
    await createDocument(values);
    setOpen(false);
    form.resetFields();
    await load();
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>知识库</h1>
          <p>管理正式知识文档，公开数据只作为测试和评估集。</p>
        </div>
        <Space>
          <Button icon={<DatabaseOutlined />} onClick={() => seedEcommerceKb().then(() => { message.success("种子知识库已导入"); load(); })}>导入电商种子</Button>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>新增文档</Button>
        </Space>
      </div>
      <Card>
        <Table
          rowKey="id"
          dataSource={docs}
          columns={[
            { title: "标题", dataIndex: "title" },
            { title: "分类", dataIndex: "category", render: (v) => <Tag>{v}</Tag> },
            { title: "来源", dataIndex: "source" },
            { title: "许可证", dataIndex: "license" },
            { title: "状态", dataIndex: "is_active", render: (v) => <Tag color={v ? "green" : "default"}>{v ? "启用" : "停用"}</Tag> }
          ]}
        />
      </Card>
      <Modal title="新增知识文档" open={open} onCancel={() => setOpen(false)} onOk={submit}>
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="category" label="分类" initialValue="通用"><Input /></Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true }]}><Input.TextArea rows={8} /></Form.Item>
        </Form>
      </Modal>
    </AuthGate>
  );
}
