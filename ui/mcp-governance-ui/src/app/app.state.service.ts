import { Injectable } from '@angular/core';

import {
  Agent,
  ApiService,
  Approval,
  AuditItem,
  CurrentUser,
  Dashboard,
  McpServer,
  SignedTool,
  Stat,
  Tool,
  ToolPolicy,
} from './api.service';

@Injectable({ providedIn: 'root' })
export class AppStateService {
  currentUser: CurrentUser | null = null;
  checkingSession = true;

  stats: Stat[] = [];
  toolPolicies: ToolPolicy[] = [];
  auditTrail: AuditItem[] = [];
  signedTools: SignedTool[] = [];
  policyYaml = '';
  lastDeployment = 'loading...';
  agents: Agent[] = [];
  servers: McpServer[] = [];
  tools: Tool[] = [];
  users: CurrentUser[] = [];
  approvals: Approval[] = [];
  unacknowledgedAlertCount = 0;
  pendingApprovalCount = 0;

  constructor(private readonly api: ApiService) {}

  init(): void {
    this.api.me().subscribe({
      next: (user) => this.afterLogin(user),
      error: () => {
        this.currentUser = null;
        this.checkingSession = false;
      },
    });
  }

  afterLogin(user: CurrentUser): void {
    this.currentUser = user;
    this.checkingSession = false;
    this.refreshAll();
    if (user.role === 'admin') {
      this.loadUsers();
    }
    this.refreshAlertCount();
    this.refreshApprovals();
    setInterval(() => this.refreshAlertCount(), 30_000);
    setInterval(() => this.refreshApprovals(), 8_000);
  }

  refreshAlertCount(): void {
    this.api.getUnacknowledgedAlertCount().subscribe((r) => (this.unacknowledgedAlertCount = r.count));
  }

  refreshApprovals(): void {
    this.api.getApprovals().subscribe((items) => (this.approvals = items));
    this.api.getPendingApprovalCount().subscribe((r) => (this.pendingApprovalCount = r.count));
  }

  refreshAll(): void {
    this.api.getDashboard().subscribe({
      next: (d: Dashboard) => {
        this.lastDeployment = d.lastDeployment;
        this.stats = d.stats;
        this.toolPolicies = d.toolPolicies;
        this.signedTools = d.signedTools;
        this.policyYaml = d.policyYaml;
      },
      error: (err) => {
        if (err?.status === 401) {
          this.currentUser = null;
        }
      },
    });
    this.api.getAgents().subscribe((a) => (this.agents = a));
    this.api.getServers().subscribe((s) => (this.servers = s));
    this.api.getTools().subscribe((t) => (this.tools = t));
    this.refreshAudit();
  }

  refreshAudit(): void {
    this.api.getAudit().subscribe((items) => (this.auditTrail = items));
  }

  loadUsers(): void {
    this.api.listUsers().subscribe((u) => (this.users = u));
  }

  toolsForServer(serverSlug: string): Tool[] {
    return this.tools.filter((t) => t.server === serverSlug);
  }
}
