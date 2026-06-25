import axios from "axios";

export type ConversationStatus = "ai" | "waiting_agent" | "human" | "closed";
export type TicketPriority = "low" | "normal" | "high" | "urgent";

export interface Conversation {
  id: number;
  visitor_name: string;
  visitor_contact: string;
  channel: string;
  status: ConversationStatus;
  assigned_agent_id?: number;
  intent: string;
  priority: TicketPriority;
  satisfaction?: number;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  sender: "visitor" | "ai" | "agent" | "system";
  content: string;
  confidence: number;
  intent: string;
  sources: Array<Record<string, unknown>>;
  created_at: string;
}

export interface KnowledgeDocument {
  id: number;
  title: string;
  category: string;
  source: string;
  license: string;
  is_active: boolean;
  created_at: string;
}

export interface Ticket {
  id: number;
  conversation_id?: number;
  title: string;
  description: string;
  status: string;
  priority: TicketPriority;
  assignee_id?: number;
  created_by_id?: number;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AnalyticsOverview {
  conversations: number;
  waiting_agent: number;
  tickets_open: number;
  knowledge_documents: number;
  ai_resolution_rate: number;
  model_cost?: number;
  knowledge_hit_rate?: number;
  quality_score?: number;
}

export interface Tenant {
  id: number;
  slug: string;
  name: string;
  plan: string;
  is_active: boolean;
}

export interface Channel {
  id: number;
  name: string;
  type: string;
  enabled: boolean;
}

export interface ModelProvider {
  id: number;
  name: string;
  provider_type: string;
  model: string;
  enabled: boolean;
}

export interface ModelCallLog {
  id: number;
  provider: string;
  model: string;
  prompt_version: string;
  input_summary: string;
  output_summary: string;
  latency_ms: number;
  cost: number;
  created_at: string;
}

export type VideoAuditStatus = "queued" | "processing" | "completed" | "needs_review" | "failed";
export type VideoRiskLevel = "low" | "medium" | "high" | "critical" | "needs_review";
export type AgentRunStatus = "running" | "waiting_review" | "waiting_remediation" | "completed" | "failed";
export type AgentStepStatus = "pending" | "running" | "completed" | "failed";
export type VideoAuditReviewDecision = "confirmed_violation" | "false_positive" | "needs_more_evidence";
export type TicketVerificationStatus = "passed" | "failed" | "needs_review";

export interface VideoAudit {
  id: number;
  file_name: string;
  content_type: string;
  status: VideoAuditStatus;
  risk_level: VideoRiskLevel;
  summary: string;
  error: string;
  duration_ms: number;
  created_ticket_id?: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface VideoAuditFinding {
  id: number;
  audit_id: number;
  category: string;
  label: string;
  risk_level: VideoRiskLevel;
  confidence: number;
  start_ms: number;
  end_ms: number;
  bbox?: [number, number, number, number] | null;
  reason: string;
  recommendation: string;
}

export interface VideoAuditEvidence {
  id: number;
  audit_id: number;
  finding_id?: number;
  timestamp_ms: number;
  frame_object_key: string;
  caption: string;
  model_score: number;
}

export interface VideoAuditReport {
  id: number;
  audit_id: number;
  report: Record<string, unknown>;
  model_version: string;
  processing_ms: number;
  created_at: string;
}

export interface VideoAuditAgentRun {
  id: number;
  audit_id: number;
  status: AgentRunStatus;
  goal: string;
  current_step: string;
  current_stage: string;
  paused_reason: string;
  decision: Record<string, unknown>;
  final_decision: Record<string, unknown>;
  error: string;
  started_at: string;
  completed_at?: string;
}

export interface VideoAuditAgentStep {
  id: number;
  run_id: number;
  audit_id: number;
  step_order: number;
  tool_name: string;
  status: AgentStepStatus;
  input_summary: string;
  output_summary: string;
  detail: Record<string, unknown>;
  artifact_refs: Array<Record<string, unknown>>;
  latency_ms: number;
  error: string;
  created_at: string;
}

export interface VideoMemorySegment {
  id: number;
  audit_id: number;
  start_ms: number;
  end_ms: number;
  frame_index: number;
  frame_object_key: string;
  visible_objects: string[];
  risk_subject: string;
  bbox?: [number, number, number, number] | null;
  evidence: string;
  raw_finding: Record<string, unknown>;
  vlm_raw_output: Record<string, unknown>;
  review_status: string;
}

export interface SafetyPolicy {
  id: number;
  code: string;
  label: string;
  title: string;
  description: string;
  severity: VideoRiskLevel;
  auto_alert: boolean;
  requires_review: boolean;
  recommend_ticket: boolean;
  requires_verification: boolean;
  due_hours: number;
  keywords: string[];
}

export interface VideoAuditReview {
  id: number;
  audit_id: number;
  reviewer_id?: number;
  decision: VideoAuditReviewDecision;
  comment: string;
  created_at: string;
}

export interface VideoAuditAlertEvent {
  id: number;
  audit_id: number;
  channel: string;
  status: string;
  risk_level: VideoRiskLevel;
  message: string;
  error: string;
  created_at: string;
}

export interface VideoAuditDetail {
  audit: VideoAudit;
  findings: VideoAuditFinding[];
  evidences: VideoAuditEvidence[];
  report?: VideoAuditReport;
  agent_run?: VideoAuditAgentRun;
  agent_steps: VideoAuditAgentStep[];
  memory_segments: VideoMemorySegment[];
  matched_rules: SafetyPolicy[];
  agent_decision: Record<string, unknown>;
  reviews: VideoAuditReview[];
  alert_events: VideoAuditAlertEvent[];
}

export interface VideoAuditMetrics {
  total: number;
  completed: number;
  high_risk: number;
  needs_review: number;
  tickets_created: number;
  generated_at: string;
}

export interface AgentOverviewMetrics {
  agent_runs: number;
  completed_runs: number;
  failed_runs: number;
  waiting_review_runs: number;
  waiting_remediation_runs: number;
  alert_events: number;
  sent_alerts: number;
  human_reviews: number;
  avg_processing_ms: number;
  generated_at: string;
}

export interface EvaluationMetrics {
  total_videos: number;
  processed_videos: number;
  processing_success_rate: number;
  total_findings: number;
  bbox_valid_findings: number;
  bbox_valid_rate: number;
  high_risk_alerts: number;
  feishu_alert_success_rate: number;
  human_review_count: number;
  human_review_confirm_rate: number;
  false_positive_rate: number;
  verification_count: number;
  verification_passed: number;
  avg_processing_ms: number;
  generated_at: string;
}

export interface SafetyTool {
  name: string;
  description: string;
}

export interface AgentExplanation {
  summary: string;
  what_agent_saw: Array<Record<string, unknown>>;
  why_this_risk: string[];
  why_this_action: string;
  tools_used: Array<Record<string, unknown>>;
  matched_policies: string[];
  alert_status: string;
  final_decision: Record<string, unknown>;
}

export interface TicketVerification {
  id: number;
  ticket_id: number;
  audit_id?: number;
  object_key: string;
  content_type: string;
  status: TicketVerificationStatus;
  summary: string;
  result: Record<string, unknown>;
  created_at: string;
  completed_at?: string;
}

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = String(error.config?.url || "");
    if (status === 401 && !url.includes("/auth/login")) {
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      localStorage.removeItem("display_name");
      window.dispatchEvent(new Event("auth-changed"));
    }
    return Promise.reject(error);
  }
);

export function getApiErrorMessage(error: unknown, fallback = "请求失败") {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join("；");
    if (error.response?.status === 401) return "登录已过期，请重新登录";
    if (error.response?.status) return `服务返回 ${error.response.status}`;
    if (error.message) return error.message;
  }
  return fallback;
}

export async function login(username: string, password: string) {
  const { data } = await api.post("/auth/login", { username, password });
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("role", data.role);
  localStorage.setItem("display_name", data.display_name);
  window.dispatchEvent(new Event("auth-changed"));
  return data;
}

export async function getOverview() {
  const { data } = await api.get<AnalyticsOverview>("/analytics/overview");
  return data;
}

export async function createChatSession(visitor_name = "网页访客") {
  const { data } = await api.post<Conversation>("/chat/sessions", { visitor_name });
  return data;
}

export async function sendChatMessage(conversationId: number, content: string) {
  const { data } = await api.post<Message[]>(`/chat/sessions/${conversationId}/messages`, { content });
  return data;
}

export async function getConversationMessages(conversationId: number) {
  const { data } = await api.get<Message[]>(`/chat/sessions/${conversationId}/messages`);
  return data;
}

export async function handoff(conversationId: number) {
  const { data } = await api.post(`/chat/sessions/${conversationId}/handoff`);
  return data;
}

export async function rateSatisfaction(conversationId: number, score: number) {
  const { data } = await api.post(`/chat/sessions/${conversationId}/satisfaction`, { score });
  return data;
}

export async function listConversations() {
  const { data } = await api.get<Conversation[]>("/agent/conversations");
  return data;
}

export async function acceptConversation(id: number) {
  const { data } = await api.post<Conversation>(`/agent/conversations/${id}/accept`);
  return data;
}

export async function agentReply(id: number, content: string) {
  const { data } = await api.post<Message>(`/agent/conversations/${id}/reply`, { content });
  return data;
}

export async function closeConversation(id: number) {
  const { data } = await api.post<Conversation>(`/agent/conversations/${id}/close`);
  return data;
}

export async function listDocuments() {
  const { data } = await api.get<KnowledgeDocument[]>("/kb/documents");
  return data;
}

export async function createDocument(payload: { title: string; category: string; content: string }) {
  const { data } = await api.post<KnowledgeDocument>("/kb/documents", payload);
  return data;
}

export async function seedEcommerceKb() {
  const { data } = await api.post("/kb/seed/ecommerce");
  return data;
}

export async function listTickets() {
  const { data } = await api.get<Ticket[]>("/tickets");
  return data;
}

export async function createTicket(payload: { title: string; description: string; priority: TicketPriority; conversation_id?: number }) {
  const { data } = await api.post<Ticket>("/tickets", payload);
  return data;
}

export async function listUsers() {
  const { data } = await api.get<User[]>("/users");
  return data;
}

export async function listTenants() {
  const { data } = await api.get<Tenant[]>("/tenants");
  return data;
}

export async function listChannels() {
  const { data } = await api.get<Channel[]>("/channels");
  return data;
}

export async function simulateWebhook(channelId: number, content: string) {
  const { data } = await api.post(`/channels/${channelId}/simulate-webhook`, { content, visitor_name: "模拟访客" });
  return data;
}

export async function listModelProviders() {
  const { data } = await api.get<ModelProvider[]>("/models/providers");
  return data;
}

export async function listModelCallLogs() {
  const { data } = await api.get<ModelCallLog[]>("/model-call-logs");
  return data;
}

export async function listPromptVersions() {
  const { data } = await api.get<Array<Record<string, unknown>>>("/prompts/versions");
  return data;
}

export async function listKnowledgeVersions() {
  const { data } = await api.get<Array<Record<string, unknown>>>("/kb/versions");
  return data;
}

export async function listQualityRules() {
  const { data } = await api.get<Array<Record<string, unknown>>>("/quality/rules");
  return data;
}

export async function runQualityReports() {
  const { data } = await api.post<Record<string, unknown>>("/quality/reports/run");
  return data;
}

export async function getSystemHealth() {
  const { data } = await api.get<Record<string, string>>("/system/health");
  return data;
}

export async function listVideoAudits() {
  const { data } = await api.get<VideoAudit[]>("/video-audits");
  return data;
}

export async function createVideoAudit(file: File) {
  const payload = new FormData();
  payload.append("file", file);
  const { data } = await api.post<VideoAudit>("/video-audits", payload);
  return data;
}

export async function getVideoAudit(id: number) {
  const { data } = await api.get<VideoAuditDetail>(`/video-audits/${id}`);
  return data;
}

export async function createVideoAuditTicket(id: number) {
  const { data } = await api.post<{ ticket_id: number; audit_id: number }>(`/video-audits/${id}/tickets`);
  return data;
}

export async function getVideoAuditMetrics() {
  const { data } = await api.get<VideoAuditMetrics>("/video-audits/metrics/overview");
  return data;
}

export async function getAgentOverviewMetrics() {
  const { data } = await api.get<AgentOverviewMetrics>("/video-audits/metrics/agent-overview");
  return data;
}

export async function getEvaluationMetrics() {
  const { data } = await api.get<EvaluationMetrics>("/video-audits/metrics/evaluation");
  return data;
}

export async function listSafetyPolicies() {
  const { data } = await api.get<SafetyPolicy[]>("/safety-policies");
  return data;
}

export async function updateSafetyPolicy(id: number, payload: Partial<SafetyPolicy>) {
  const { data } = await api.patch<SafetyPolicy>(`/safety-policies/${id}`, payload);
  return data;
}

export async function listSafetyTools() {
  const { data } = await api.get<SafetyTool[]>("/safety-tools");
  return data;
}

export async function reviewVideoAudit(id: number, payload: { decision: VideoAuditReviewDecision; comment?: string }) {
  const { data } = await api.post<VideoAuditReview>(`/video-audits/${id}/review`, payload);
  return data;
}

export async function resumeVideoAudit(id: number) {
  const { data } = await api.post<{ audit: VideoAudit; agent_run: VideoAuditAgentRun; agent_decision: Record<string, unknown> }>(`/video-audits/${id}/resume`);
  return data;
}

export async function getVideoAuditMemory(id: number, params?: { label?: string; review_status?: string; has_bbox?: boolean }) {
  const { data } = await api.get<VideoMemorySegment[]>(`/video-audits/${id}/memory`, { params });
  return data;
}

export async function getVideoAuditAgentExplanation(id: number) {
  const { data } = await api.get<AgentExplanation>(`/video-audits/${id}/agent-explanation`);
  return data;
}

export async function getEvidenceImage(auditId: number, evidenceId: number) {
  const { data } = await api.get<Blob>(`/video-audits/${auditId}/evidence/${evidenceId}/image`, { responseType: "blob" });
  return URL.createObjectURL(data);
}

export async function listTicketVerifications(ticketId: number) {
  const { data } = await api.get<TicketVerification[]>(`/tickets/${ticketId}/verification`);
  return data;
}

export async function createTicketVerification(ticketId: number, file: File) {
  const payload = new FormData();
  payload.append("file", file);
  const { data } = await api.post<TicketVerification>(`/tickets/${ticketId}/verification`, payload);
  return data;
}
