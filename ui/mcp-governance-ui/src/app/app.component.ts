import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  API_BASE,
  Agent,
  ApiService,
  AuditItem,
  CurrentUser,
  GatewayInvokeResult,
  McpServer,
  SignedTool,
  Stat,
  Tool,
  ToolPolicy,
} from './api.service';

interface ToolParamField {
  name: string;
  type: string;
  required: boolean;
  isJson: boolean;
}

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  title = 'Falcon';
  activeNav = 'Overview';
  lastDeployment = 'loading...';
  loading = true;
  errorMessage = '';

  // Auth: null + checkingSession=true means "still resolving the session on
  // load"; null + checkingSession=false means "show the login screen".
  currentUser: CurrentUser | null = null;
  checkingSession = true;
  loginForm = { username: '', password: '' };
  loginError = '';
  loggingIn = false;

  users: CurrentUser[] = [];
  createUserForm = { username: '', role: 'user' };
  creatingUser = false;
  // Set only right after a successful create call -- the temp password is
  // never returned again, so this is shown once and cleared on dismiss.
  newUserCreated: { username: string; password: string } | null = null;

  changePasswordForm = { currentPassword: '', newPassword: '', confirmPassword: '' };
  changingPassword = false;
  changePasswordError = '';
  changePasswordSuccess = false;

  stats: Stat[] = [];
  toolPolicies: ToolPolicy[] = [];
  auditTrail: AuditItem[] = [];
  signedTools: SignedTool[] = [];
  policyYaml = '';

  agents: Agent[] = [];
  servers: McpServer[] = [];
  tools: Tool[] = [];

  navItems = ['Overview', 'Agents', 'Servers', 'Policies', 'Gateway', 'Audit', 'Account'];

  invokeForm = {
    agent: '',
    server: '',
    tool: '',
    user: '',
  };
  // Raw string values keyed by param name, populated from the selected
  // tool's MCP inputSchema -- see onInvokeToolChange().
  invokeParamValues: Record<string, string> = {};
  invokeResult: GatewayInvokeResult | null = null;
  invoking = false;

  addServerForm = {
    slug: '',
    name: '',
    endpoint: '',
    trust: 'Needs review',
  };
  addingServer = false;
  editingServerSlug: string | null = null;

  registerAgentForm = {
    name: '',
    owner: '',
    environment: 'Production',
    tools_allowed: 0,
  };
  registeringAgent = false;
  // Set only right after a successful register call -- the API key is never
  // returned again, so this is shown once and cleared on dismiss.
  newAgentApiKey: { name: string; key: string } | null = null;

  ruleBuilderForm = {
    agentScope: '',
    server: '',
    tool: '*',
    action: 'allow',
  };
  addingRule = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.me().subscribe({
      next: (user) => this.onLoggedIn(user),
      error: () => {
        this.currentUser = null;
        this.checkingSession = false;
      },
    });
  }

  private onLoggedIn(user: CurrentUser): void {
    this.currentUser = user;
    this.checkingSession = false;
    this.refreshAll();
    if (user.role === 'admin') {
      this.loadUsers();
    }
  }

  visibleNavItems(): string[] {
    return this.currentUser?.role === 'admin' ? [...this.navItems, 'Users'] : this.navItems;
  }

  login(): void {
    if (!this.loginForm.username || !this.loginForm.password) {
      return;
    }
    this.loggingIn = true;
    this.loginError = '';
    this.api.login(this.loginForm.username, this.loginForm.password).subscribe({
      next: (user) => {
        this.loggingIn = false;
        this.loginForm = { username: '', password: '' };
        this.onLoggedIn(user);
      },
      error: (err) => {
        this.loggingIn = false;
        this.loginError = err?.error?.detail ?? 'Login failed.';
      },
    });
  }

  logout(): void {
    this.api.logout().subscribe(() => {
      this.currentUser = null;
      this.activeNav = 'Overview';
      this.users = [];
    });
  }

  loadUsers(): void {
    this.api.listUsers().subscribe((users) => (this.users = users));
  }

  createUser(): void {
    if (!this.createUserForm.username) {
      return;
    }
    this.creatingUser = true;
    this.api.createUser(this.createUserForm).subscribe({
      next: (created) => {
        this.creatingUser = false;
        this.newUserCreated = { username: created.username, password: created.temp_password };
        this.createUserForm = { username: '', role: 'user' };
        this.loadUsers();
      },
      error: (err) => {
        this.creatingUser = false;
        this.errorMessage = err?.error?.detail ?? 'Failed to create user.';
      },
    });
  }

  dismissNewUserCreated(): void {
    this.newUserCreated = null;
  }

  changePassword(): void {
    const { currentPassword, newPassword, confirmPassword } = this.changePasswordForm;
    this.changePasswordError = '';
    this.changePasswordSuccess = false;

    if (!currentPassword || !newPassword) {
      return;
    }
    if (newPassword !== confirmPassword) {
      this.changePasswordError = 'New password and confirmation do not match.';
      return;
    }

    this.changingPassword = true;
    this.api.changePassword(currentPassword, newPassword).subscribe({
      next: () => {
        this.changingPassword = false;
        this.changePasswordSuccess = true;
        this.changePasswordForm = { currentPassword: '', newPassword: '', confirmPassword: '' };
      },
      error: (err) => {
        this.changingPassword = false;
        this.changePasswordError = err?.error?.detail ?? 'Failed to change password.';
      },
    });
  }

  private refreshAll(): void {
    this.loading = true;
    this.api.getDashboard().subscribe({
      next: (dashboard) => {
        this.lastDeployment = dashboard.lastDeployment;
        this.stats = dashboard.stats;
        this.toolPolicies = dashboard.toolPolicies;
        this.auditTrail = dashboard.auditTrail;
        this.signedTools = dashboard.signedTools;
        this.policyYaml = dashboard.policyYaml;
        this.loading = false;
      },
      error: (err) => {
        if (err?.status === 401) {
          this.currentUser = null;
          this.loading = false;
          return;
        }
        this.errorMessage = 'Could not reach the control plane API at http://localhost:8000. Is the backend running?';
        this.loading = false;
      },
    });

    this.api.getAgents().subscribe((agents) => (this.agents = agents));
    this.api.getServers().subscribe((servers) => {
      this.servers = servers;
      if (!this.ruleBuilderForm.server && servers.length) {
        this.ruleBuilderForm.server = servers[0].slug;
      }
    });
    this.api.getTools().subscribe((tools) => {
      this.tools = tools;
      if (!this.invokeForm.server && tools.length) {
        this.invokeForm.server = tools[0].server;
        this.invokeForm.tool = tools[0].name;
      }
    });
  }

  setActiveNav(item: string): void {
    this.activeNav = item;
  }

  gatewayUrlFor(server: McpServer): string | null {
    if (!server.endpoint.startsWith('http://') && !server.endpoint.startsWith('https://')) {
      return null;
    }
    return `${API_BASE}/mcp/${server.slug}`;
  }

  toolsForServer(serverSlug: string): Tool[] {
    return this.tools.filter((t) => t.server === serverSlug);
  }

  onInvokeServerChange(): void {
    const first = this.toolsForServer(this.invokeForm.server)[0];
    this.invokeForm.tool = first ? first.name : '';
    this.onInvokeToolChange();
  }

  onInvokeToolChange(): void {
    this.invokeParamValues = {};
  }

  selectedInvokeTool(): Tool | undefined {
    return this.toolsForServer(this.invokeForm.server).find((t) => t.name === this.invokeForm.tool);
  }

  invokeToolParamFields(): ToolParamField[] {
    const schema = this.selectedInvokeTool()?.inputSchema;
    const properties = schema?.properties ?? {};
    const required = new Set(schema?.required ?? []);
    return Object.keys(properties).map((name) => {
      const type = properties[name].type ?? 'string';
      return { name, type, required: required.has(name), isJson: type === 'object' || type === 'array' };
    });
  }

  exportPolicy(): void {
    const blob = new Blob([this.policyYaml], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'mcp-policy.yaml';
    anchor.click();
    URL.revokeObjectURL(url);
  }

  deployPolicy(): void {
    this.api.deployPolicy(this.policyYaml).subscribe({
      next: () => this.refreshAll(),
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to deploy policy: invalid YAML.';
      },
    });
  }

  addPolicyRule(): void {
    if (!this.ruleBuilderForm.server) {
      return;
    }

    this.addingRule = true;
    this.api
      .previewPolicyRule({
        yaml: this.policyYaml,
        agent: this.ruleBuilderForm.agentScope || null,
        server: this.ruleBuilderForm.server,
        tool: this.ruleBuilderForm.tool || '*',
        action: this.ruleBuilderForm.action,
      })
      .subscribe({
        next: (res) => {
          this.addingRule = false;
          this.policyYaml = res.yaml;
        },
        error: (err) => {
          this.addingRule = false;
          this.errorMessage = err?.error?.detail ?? 'Failed to build policy rule.';
        },
      });
  }

  exportAuditLog(): void {
    const blob = new Blob([JSON.stringify(this.auditTrail, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'mcp-audit-log.json';
    anchor.click();
    URL.revokeObjectURL(url);
  }

  toggleAgentStatus(name: string): void {
    this.api.toggleAgent(name).subscribe(() => this.refreshAll());
  }

  registerAgent(): void {
    if (!this.registerAgentForm.name || !this.registerAgentForm.owner) {
      return;
    }

    this.registeringAgent = true;
    this.api
      .registerAgent({ ...this.registerAgentForm, status: 'Active' })
      .subscribe({
        next: (created) => {
          this.registeringAgent = false;
          this.newAgentApiKey = { name: created.name, key: created.api_key };
          this.registerAgentForm = { name: '', owner: '', environment: 'Production', tools_allowed: 0 };
          this.refreshAll();
        },
        error: (err) => {
          this.registeringAgent = false;
          this.errorMessage = err?.error?.detail ?? 'Failed to register agent.';
        },
      });
  }

  dismissNewAgentApiKey(): void {
    this.newAgentApiKey = null;
  }

  removeAgent(name: string): void {
    if (!confirm(`Remove agent "${name}"?`)) {
      return;
    }
    this.api.removeAgent(name).subscribe({
      next: () => this.refreshAll(),
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to remove agent.';
      },
    });
  }

  syncServer(slug: string): void {
    this.api.syncServer(slug).subscribe({
      next: () => this.refreshAll(),
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to sync MCP server.';
      },
    });
  }

  addServer(): void {
    if (!this.addServerForm.slug || !this.addServerForm.name || !this.addServerForm.endpoint) {
      return;
    }

    this.addingServer = true;

    const request = this.editingServerSlug
      ? this.api.updateServer(this.editingServerSlug, {
          name: this.addServerForm.name,
          endpoint: this.addServerForm.endpoint,
          trust: this.addServerForm.trust,
        })
      : this.api.addServer(this.addServerForm);

    request.subscribe({
      next: () => {
        this.addingServer = false;
        this.cancelEditServer();
        this.refreshAll();
      },
      error: (err) => {
        this.addingServer = false;
        this.errorMessage = err?.error?.detail ?? 'Failed to save MCP server.';
      },
    });
  }

  editServer(server: McpServer): void {
    this.editingServerSlug = server.slug;
    this.addServerForm = {
      slug: server.slug,
      name: server.name,
      endpoint: server.endpoint,
      trust: server.trust,
    };
  }

  cancelEditServer(): void {
    this.editingServerSlug = null;
    this.addServerForm = { slug: '', name: '', endpoint: '', trust: 'Needs review' };
  }

  removeServer(slug: string): void {
    if (!confirm(`Remove MCP server "${slug}"? This also removes its tools and trust records.`)) {
      return;
    }
    this.api.deleteServer(slug).subscribe({
      next: () => {
        if (this.editingServerSlug === slug) {
          this.cancelEditServer();
        }
        this.refreshAll();
      },
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to remove MCP server.';
      },
    });
  }

  submitInvoke(): void {
    if (!this.invokeForm.agent || !this.invokeForm.server || !this.invokeForm.tool || !this.invokeForm.user) {
      return;
    }

    const params: Record<string, unknown> = {};
    for (const field of this.invokeToolParamFields()) {
      const raw = this.invokeParamValues[field.name];
      if (raw === undefined || raw === '') {
        continue;
      }
      if (field.isJson) {
        try {
          params[field.name] = JSON.parse(raw);
        } catch {
          this.errorMessage = `"${field.name}" must be valid JSON.`;
          return;
        }
      } else if (field.type === 'number' || field.type === 'integer') {
        params[field.name] = Number(raw);
      } else if (field.type === 'boolean') {
        params[field.name] = raw === 'true';
      } else {
        params[field.name] = raw;
      }
    }

    this.invoking = true;
    this.invokeResult = null;
    this.api
      .invokeGateway({
        agent: this.invokeForm.agent,
        server: this.invokeForm.server,
        tool: this.invokeForm.tool,
        user: this.invokeForm.user,
        params,
      })
      .subscribe({
        next: (result) => {
          this.invokeResult = result;
          this.invoking = false;
          this.refreshAll();
        },
        error: (err) => {
          this.invoking = false;
          this.errorMessage = err?.error?.detail ?? 'Gateway invocation failed.';
        },
      });
  }
}
