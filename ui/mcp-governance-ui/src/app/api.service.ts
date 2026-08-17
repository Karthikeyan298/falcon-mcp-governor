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
  status: 'Allowed' | 'Denied';
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

export interface McpServer {
  slug: string;
  name: string;
  endpoint: string;
  toolCount: number;
  trust: 'Trusted' | 'Needs review';
  lastSynced: string;
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

export interface GatewayInvokeResult {
  decision: 'allow' | 'deny';
  decisionLabel: string;
  reason: string;
  result: { ok: boolean; message: string } | null;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  getDashboard(): Observable<Dashboard> {
    return this.http.get<Dashboard>(`${API_BASE}/api/dashboard`);
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

  addServer(payload: { slug: string; name: string; endpoint: string; trust: string }): Observable<McpServer> {
    return this.http.post<McpServer>(`${API_BASE}/api/servers`, payload);
  }

  updateServer(
    slug: string,
    payload: { name: string; endpoint: string; trust: string },
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
}
