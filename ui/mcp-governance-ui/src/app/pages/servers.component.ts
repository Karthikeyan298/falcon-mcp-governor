import { Component, inject } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { API_BASE, ApiService, AuthType, CredentialConfig, McpServer } from '../api.service';
import { AppStateService } from '../app.state.service';
import { SignedToolsComponent } from '../shared/signed-tools.component';

@Component({
  selector: 'app-servers',
  imports: [NgClass, FormsModule, SignedToolsComponent],
  templateUrl: './servers.component.html',
})
export class ServersComponent {
  protected state = inject(AppStateService);
  private api = inject(ApiService);

  form = { slug: '', name: '', endpoint: '', trust: 'Needs review' };
  cred: CredentialConfig = { type: 'none' };
  saving = false;
  editingSlug: string | null = null;
  errorMessage = '';

  readonly authTypeLabels: Record<AuthType, string> = {
    none:    'No authentication',
    bearer:  'Bearer token',
    api_key: 'API key header',
    basic:   'Basic auth (username / password)',
  };

  gatewayUrlFor(server: McpServer): string | null {
    if (!server.endpoint.startsWith('http://') && !server.endpoint.startsWith('https://')) {
      return null;
    }
    return `${API_BASE}/mcp/${server.slug}`;
  }

  authBadge(authType: AuthType): string {
    return authType === 'none' ? '' : this.authTypeLabels[authType] ?? authType;
  }

  edit(server: McpServer): void {
    this.editingSlug = server.slug;
    this.form = { slug: server.slug, name: server.name, endpoint: server.endpoint, trust: server.trust };
    // Pre-select existing auth type (values are never shown back — user must re-enter)
    this.cred = { type: server.authType ?? 'none' };
  }

  cancelEdit(): void {
    this.editingSlug = null;
    this.form = { slug: '', name: '', endpoint: '', trust: 'Needs review' };
    this.cred = { type: 'none' };
  }

  private buildCredential(): CredentialConfig | undefined {
    if (this.cred.type === 'none') return undefined;
    return { ...this.cred };
  }

  save(): void {
    if (!this.form.slug || !this.form.name || !this.form.endpoint) return;
    this.saving = true;
    this.errorMessage = '';
    const credential = this.buildCredential();
    const req = this.editingSlug
      ? this.api.updateServer(this.editingSlug, {
          name: this.form.name,
          endpoint: this.form.endpoint,
          trust: this.form.trust,
          credential,
        })
      : this.api.addServer({ ...this.form, credential });
    req.subscribe({
      next: () => {
        this.saving = false;
        this.cancelEdit();
        this.state.refreshAll();
      },
      error: (err) => {
        this.saving = false;
        this.errorMessage = err?.error?.detail ?? 'Failed to save MCP server.';
      },
    });
  }

  sync(slug: string): void {
    this.api.syncServer(slug).subscribe({
      next: () => this.state.refreshAll(),
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to sync MCP server.';
      },
    });
  }

  remove(slug: string): void {
    if (!confirm(`Remove MCP server "${slug}"? This also removes its tools and trust records.`)) return;
    this.api.deleteServer(slug).subscribe({
      next: () => {
        if (this.editingSlug === slug) this.cancelEdit();
        this.state.refreshAll();
      },
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to remove MCP server.';
      },
    });
  }
}
