import { Card, Table, Tag, message } from "antd";
import { useEffect, useState } from "react";
import AuthGate from "../components/AuthGate";
import { listUsers, User } from "../services/api";

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    listUsers().then(setUsers).catch(() => message.error("加载用户失败"));
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>用户权限</h1>
          <p>当前实现 RBAC 基础角色，后续可扩展部门和数据权限。</p>
        </div>
      </div>
      <Card>
        <Table
          rowKey="id"
          dataSource={users}
          columns={[
            { title: "用户名", dataIndex: "username" },
            { title: "姓名", dataIndex: "display_name" },
            { title: "角色", dataIndex: "role", render: (v) => <Tag>{v}</Tag> },
            { title: "状态", dataIndex: "is_active", render: (v) => <Tag color={v ? "green" : "default"}>{v ? "启用" : "停用"}</Tag> }
          ]}
        />
      </Card>
    </AuthGate>
  );
}
