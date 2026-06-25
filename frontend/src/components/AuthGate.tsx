import { Button, Form, Input, message } from "antd";
import { ReactNode, useEffect, useState } from "react";
import { login } from "../services/api";

interface Props {
  children: ReactNode;
}

export default function AuthGate({ children }: Props) {
  const [ready, setReady] = useState(Boolean(localStorage.getItem("token")));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const syncAuthState = () => setReady(Boolean(localStorage.getItem("token")));
    window.addEventListener("auth-changed", syncAuthState);
    window.addEventListener("storage", syncAuthState);
    return () => {
      window.removeEventListener("auth-changed", syncAuthState);
      window.removeEventListener("storage", syncAuthState);
    };
  }, []);

  if (ready) return <>{children}</>;

  return (
    <div className="auth-card">
      <h2>登录管理后台</h2>
      <Form
        layout="vertical"
        initialValues={{ username: "admin", password: "Admin123!" }}
        onFinish={async (values) => {
          setLoading(true);
          try {
            await login(values.username, values.password);
            setReady(true);
          } catch {
            message.error("登录失败");
          } finally {
            setLoading(false);
          }
        }}
      >
        <Form.Item label="用户名" name="username">
          <Input />
        </Form.Item>
        <Form.Item label="密码" name="password">
          <Input.Password />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          登录
        </Button>
      </Form>
    </div>
  );
}
