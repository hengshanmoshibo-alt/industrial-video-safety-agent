import {
  AuditOutlined,
  BarChartOutlined,
  BranchesOutlined,
  FileDoneOutlined,
  SafetyCertificateOutlined
} from "@ant-design/icons";
import { Layout, Menu, Spin, Typography } from "antd";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";

const { Header, Sider, Content } = Layout;

type PageKey = "safety" | "agent_trace" | "review" | "tickets" | "evaluation";

const SafetyInspection = lazy(() => import("./pages/SafetyInspection"));
const AgentTrace = lazy(() => import("./pages/AgentTrace"));
const HumanReview = lazy(() => import("./pages/HumanReview"));
const Tickets = lazy(() => import("./pages/Tickets"));
const EvaluationPanel = lazy(() => import("./pages/EvaluationPanel"));

export default function App() {
  const [page, setPage] = useState<PageKey>("safety");
  const [role, setRole] = useState(localStorage.getItem("role") || "guest");

  useEffect(() => {
    const refreshRole = () => setRole(localStorage.getItem("role") || "guest");
    window.addEventListener("auth-changed", refreshRole);
    window.addEventListener("storage", refreshRole);
    return () => {
      window.removeEventListener("auth-changed", refreshRole);
      window.removeEventListener("storage", refreshRole);
    };
  }, []);

  const menuItems = useMemo(() => {
    const all = [
      { key: "safety", icon: <SafetyCertificateOutlined />, label: "安全巡检", roles: ["admin", "supervisor", "auditor", "agent"] },
      { key: "agent_trace", icon: <BranchesOutlined />, label: "Agent 执行轨迹", roles: ["admin", "supervisor", "auditor", "agent"] },
      { key: "review", icon: <AuditOutlined />, label: "人工复核", roles: ["admin", "supervisor", "auditor"] },
      { key: "tickets", icon: <FileDoneOutlined />, label: "整改工单", roles: ["admin", "supervisor", "agent", "auditor"] },
      { key: "evaluation", icon: <BarChartOutlined />, label: "评估面板", roles: ["admin", "supervisor", "auditor"] }
    ];
    const visible = all.filter((item) => role === "guest" || item.roles.includes(role));
    return visible.map(({ roles, ...item }) => item);
  }, [role]);

  const pageNode = useMemo(() => {
    switch (page) {
      case "agent_trace":
        return <AgentTrace />;
      case "review":
        return <HumanReview />;
      case "tickets":
        return <Tickets />;
      case "evaluation":
        return <EvaluationPanel />;
      case "safety":
      default:
        return <SafetyInspection />;
    }
  }, [page]);

  return (
    <Layout className="app-shell">
      <Sider width={236} theme="light" className="sidebar">
        <div className="brand">
          <SafetyCertificateOutlined />
          <div>
            <Typography.Title level={4}>安全巡检 Agent</Typography.Title>
            <Typography.Text type="secondary">工业/仓储演示版</Typography.Text>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[page]}
          onClick={(item) => setPage(item.key as PageKey)}
          items={menuItems}
        />
      </Sider>
      <Layout>
        <Header className="topbar">
          <Typography.Text strong>工业安全巡检与整改闭环平台</Typography.Text>
          <Typography.Text type="secondary">默认账号 admin / Admin123!</Typography.Text>
        </Header>
        <Content className="content">
          <Suspense fallback={<Spin className="page-loading" />}>{pageNode}</Suspense>
        </Content>
      </Layout>
    </Layout>
  );
}
