import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export const API_BASE = 'http://localhost:8000';

export interface CurrentUser {
  id: number;
  username: string;
  role: 'admin' | 'user';
  status: 'Active' | 'Suspended';
}

export interface UserCreated extends CurrentUser {
  // Only present on the create response -- the temp password is never
  // stored in plaintext or returned again.
  temp_password: string;
}

export interface Stat {
  label: string;
  value: string;
  delta: string;
}

export interface ToolPolicy {
  name: string;
  server: string;
  status: 'Allowed' | 'Denied' | 'Require approval';
  signed: boolean;
  risk: 'Low' | 'Medium' | 'High';
  environment: 'Production' | 'Staging' | 'Dev';
}

export interface AuditItem {
  time: string;
  agent: string;
  tool: string;
  action: string;
  decision: 'Allowed' | 'Denied';
  user: string;
}

export interface SignedTool {
  name: string;
  publisher: string;
  status: 'Verified' | 'Needs approval' | 'Revoked';
  hash: string;
}

export interface Agent {
  name: string;
  owner: string;
  environment: 'Production' | 'Staging' | 'Dev';
  tools_allowed: number;
  status: 'Active' | 'Suspended';
}

export interface AgentCreated extends Agent {
  // Only present on the create response -- the raw key is never stored or
  // returned again, so the UI must show it once and prompt the user to copy it.
  api_key: string;
}

export type AuthType = 'none' | 'bearer' | 'api_key' | 'basic';

export interface CredentialConfig {
  type: AuthType;
  token?: string;
  header_name?: string;
  header_value?: string;
  username?: string;
  password?: string;
}

export interface McpServer {
  slug: string;
  name: string;
  endpoint: string;
  toolCount: number;
  trust: 'Trusted' | 'Needs review';
  lastSynced: string;
  authType: AuthType;
}

export interface ToolInputSchemaProperty {
  type?: string;
  title?: string;
}

export interface ToolInputSchema {
  properties?: Record<string, ToolInputSchemaProperty>;
  required?: string[];
}

export interface Tool {
  server: string;
  name: string;
  risk: string;
  environment: string;
  inputSchema: ToolInputSchema | null;
}

export interface Dashboard {
  lastDeployment: string;
  stats: Stat[];
  toolPolicies: ToolPolicy[];
  auditTrail: AuditItem[];
  signedTools: SignedTool[];
  policyYaml: string;
}

export interface Alert {
  id: number;
  type: 'repeated_denials' | 'high_call_rate' | 'new_tool_attempt' | 'approval_flood';
  severity: 'low' | 'medium' | 'high';
  agent: string;
  server: string | null;
  tool: string | null;
  message: string;
  createdAt: string;
  acknowledgedAt: string | null;
  acknowledgedBy: string | null;
}

export interface AlertRule {
  enabled: boolean;
  threshold?: number;
  window_minutes?: number;
  severity: 'low' | 'medium' | 'high';
}

export interface AlertRules {
  repeated_denials: AlertRule;
  high_call_rate: AlertRule;
  new_tool_attempt: AlertRule;
  approval_flood: AlertRule;
}

export interface Approval {
  id: number;
  agent: string;
  server: string;
  tool: string;
  arguments: Record<string, unknown>;
  user: string;
  status: 'pending' | 'approved' | 'denied' | 'executed';
  decisionBy: string | null;
  decidedAt: string | null;
  createdAt: string;
  result: string | null;
}

export interface ToolMatrixRow {
  name: string;
  server: string;
  serverSlug: string;
  status: 'Allowed' | 'Denied' | 'Require approval';
  signed: boolean;
  risk: string;
  environment: string;
}

export interface GatewayInvokeResult {
  decision: 'allow' | 'deny';
  decisionLabel: string;
  reason: string;
  result: { ok: boolean; message: string } | null;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private readonly http: HttpClient) {}

  getDashboard(): Observable<Dashboard> {
    return this.http.get<Dashboard>(`${API_BASE}/api/dashboard`);
  }

  getAudit(): Observable<AuditItem[]> {
    return this.http.get<AuditItem[]>(`${API_BASE}/api/audit`);
  }

  getAgents(): Observable<Agent[]> {
    return this.http.get<Agent[]>(`${API_BASE}/api/agents`);
  }

  toggleAgent(name: string): Observable<Agent> {
    return this.http.post<Agent>(`${API_BASE}/api/agents/${encodeURIComponent(name)}/toggle`, {});
  }

  registerAgent(payload: {
    name: string;
    owner: string;
    environment: string;
    tools_allowed: number;
    status: string;
  }): Observable<AgentCreated> {
    return this.http.post<AgentCreated>(`${API_BASE}/api/agents`, payload);
  }

  removeAgent(name: string): Observable<{ status: string; name: string }> {
    return this.http.delete<{ status: string; name: string }>(`${API_BASE}/api/agents/${encodeURIComponent(name)}`);
  }

  getServers(): Observable<McpServer[]> {
    return this.http.get<McpServer[]>(`${API_BASE}/api/servers`);
  }

  syncServer(slug: string): Observable<McpServer> {
    return this.http.post<McpServer>(`${API_BASE}/api/servers/${encodeURIComponent(slug)}/sync`, {});
  }

  addServer(payload: { slug: string; name: string; endpoint: string; trust: string; credential?: CredentialConfig }): Observable<McpServer> {
    return this.http.post<McpServer>(`${API_BASE}/api/servers`, payload);
  }

  updateServer(
    slug: string,
    payload: { name: string; endpoint: string; trust: string; credential?: CredentialConfig },
  ): Observable<McpServer> {
    return this.http.put<McpServer>(`${API_BASE}/api/servers/${encodeURIComponent(slug)}`, payload);
  }

  deleteServer(slug: string): Observable<{ status: string; slug: string }> {
    return this.http.delete<{ status: string; slug: string }>(
      `${API_BASE}/api/servers/${encodeURIComponent(slug)}`,
    );
  }

  getTools(): Observable<Tool[]> {
    return this.http.get<Tool[]>(`${API_BASE}/api/tools`);
  }

  deployPolicy(yamlText: string): Observable<{ status: string; lastDeployment: string }> {
    return this.http.post<{ status: string; lastDeployment: string }>(`${API_BASE}/api/policies/deploy`, {
      yaml: yamlText,
    });
  }

  getToolMatrix(agent?: string): Observable<ToolMatrixRow[]> {
    const params: Record<string, string> = {};
    if (agent) params['agent'] = agent;
    return this.http.get<ToolMatrixRow[]>(`${API_BASE}/api/policies/tool-matrix`, { params });
  }

  previewPolicyRule(payload: {
    yaml: string;
    agent: string | null;
    server: string;
    tool: string;
    action: string;
  }): Observable<{ yaml: string }> {
    return this.http.post<{ yaml: string }>(`${API_BASE}/api/policies/rule-preview`, payload);
  }

  invokeGateway(payload: {
    agent: string;
    server: string;
    tool: string;
    user: string;
    params: Record<string, unknown>;
  }): Observable<GatewayInvokeResult> {
    return this.http.post<GatewayInvokeResult>(`${API_BASE}/api/gateway/invoke`, payload);
  }

  login(username: string, password: string): Observable<CurrentUser> {
    return this.http.post<CurrentUser>(`${API_BASE}/api/auth/login`, { username, password });
  }

  logout(): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${API_BASE}/api/auth/logout`, {});
  }

  me(): Observable<CurrentUser> {
    return this.http.get<CurrentUser>(`${API_BASE}/api/auth/me`);
  }

  changePassword(currentPassword: string, newPassword: string): Observable<CurrentUser> {
    return this.http.post<CurrentUser>(`${API_BASE}/api/auth/password`, {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  listUsers(): Observable<CurrentUser[]> {
    return this.http.get<CurrentUser[]>(`${API_BASE}/api/users`);
  }

  createUser(payload: { username: string; role: string }): Observable<UserCreated> {
    return this.http.post<UserCreated>(`${API_BASE}/api/users`, payload);
  }

  previewPolicyParamRule(payload: {
    yaml: string;
    agent: string | null;
    server: string;
    tool: string;
    param: string;
    operator: string;
    value: string;
    decision: string;
    reason: string;
  }): Observable<{ yaml: string }> {
    return this.http.post<{ yaml: string }>(`${API_BASE}/api/policies/param-rule-preview`, payload);
  }

  getAlerts(): Observable<Alert[]> {
    return this.http.get<Alert[]>(`${API_BASE}/api/alerts`);
  }

  getUnacknowledgedAlertCount(): Observable<{ count: number }> {
    return this.http.get<{ count: number }>(`${API_BASE}/api/alerts/unacknowledged-count`);
  }

  acknowledgeAlert(id: number): Observable<Alert> {
    return this.http.post<Alert>(`${API_BASE}/api/alerts/${id}/acknowledge`, {});
  }

  getAlertRules(): Observable<AlertRules> {
    return this.http.get<AlertRules>(`${API_BASE}/api/alert-rules`);
  }

  updateAlertRules(rules: AlertRules): Observable<AlertRules> {
    return this.http.put<AlertRules>(`${API_BASE}/api/alert-rules`, rules);
  }

  getApprovals(): Observable<Approval[]> {
    return this.http.get<Approval[]>(`${API_BASE}/api/approvals`);
  }

  getPendingApprovalCount(): Observable<{ count: number }> {
    return this.http.get<{ count: number }>(`${API_BASE}/api/approvals/pending-count`);
  }

  approveRequest(id: number): Observable<Approval> {
    return this.http.post<Approval>(`${API_BASE}/api/approvals/${id}/approve`, {});
  }

  denyRequest(id: number): Observable<Approval> {
    return this.http.post<Approval>(`${API_BASE}/api/approvals/${id}/deny`, {});
  }
}
