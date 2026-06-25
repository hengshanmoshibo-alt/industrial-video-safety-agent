import { Button, Card, Input, Space, Table, Tag, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import AuthGate from "../components/AuthGate";
import {
  getApiErrorMessage,
  listVideoAudits,
  resumeVideoAudit,
  reviewVideoAudit,
  VideoAudit,
  VideoAuditReviewDecision
} from "../services/api";

const decisionText: Record<VideoAuditReviewDecision, string> = {
  confirmed_violation: "确认为违规",
  false_positive: "判定为误报",
  needs_more_evidence: "需要补充证据"
};

export default function HumanReview() {
  const [audits, setAudits] = useState<VideoAudit[]>([]);
  const [comment, setComment] = useState("安全主管已结合原视频和证据截图完成复核。");
  const [loading, setLoading] = useState(false);

  const reviewItems = useMemo(
    () => audits.filter((item) => item.status === "needs_review" || item.risk_level === "needs_review"),
    [audits]
  );

  async function load() {
    setLoading(true);
    try {
      setAudits(await listVideoAudits());
    } catch (error) {
      message.error(`加载人工复核队列失败：${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  }

  async function submit(auditId: number, decision: VideoAuditReviewDecision) {
    try {
      await reviewVideoAudit(auditId, { decision, comment: comment || decisionText[decision] });
      await resumeVideoAudit(auditId);
      message.success("复核结论已保存，Agent 已恢复执行");
      await load();
    } catch (error) {
      message.error(`提交复核失败：${getApiErrorMessage(error)}`);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AuthGate>
      <div className="page-head">
        <div>
          <h1>人工复核</h1>
          <p>处理证据不足或需要主管确认的巡检结果，复核后 Agent 会继续后续动作。</p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </div>

      <Card className="section-card">
        <Space direction="vertical" className="full-width" size={16}>
          <Input.TextArea
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="填写本次复核意见"
          />
          <Table
            rowKey="id"
            loading={loading}
            dataSource={reviewItems}
            columns={[
              { title: "任务", dataIndex: "id", width: 90, render: (value) => `#${value}` },
              { title: "视频", dataIndex: "file_name", ellipsis: true },
              { title: "状态", dataIndex: "status", width: 120, render: (value) => <Tag>{value}</Tag> },
              { title: "风险", dataIndex: "risk_level", width: 120, render: (value) => <Tag color="purple">{value}</Tag> },
              { title: "摘要", dataIndex: "summary", ellipsis: true },
              {
                title: "复核操作",
                width: 300,
                render: (_, row: VideoAudit) => (
                  <Space wrap>
                    <Button size="small" onClick={() => submit(row.id, "confirmed_violation")}>确认违规</Button>
                    <Button size="small" onClick={() => submit(row.id, "false_positive")}>误报</Button>
                    <Button size="small" onClick={() => submit(row.id, "needs_more_evidence")}>补证据</Button>
                  </Space>
                )
              }
            ]}
          />
        </Space>
      </Card>
    </AuthGate>
  );
}
