import { Component, inject } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { API_BASE, ApiService, McpServer } from '../api.service';
import { AppStateService } from '../app.state.service';
import { SignedToolsComponent } from '../shared/signed-tools.component';

@Component({
  selector: 'app-servers',
  imports: [NgClass, FormsModule, SignedToolsComponent],
  templateUrl: './servers.component.html',
})
export class ServersComponent {
  protected state = inject(AppStateService);
  private readonly api = inject(ApiService);

  form = { slug: '', name: '', endpoint: '', trust: 'Needs review' };
  saving = false;
  editingSlug: string | null = null;
  errorMessage = '';

  gatewayUrlFor(server: McpServer): string {
    return `${API_BASE}/mcp/${server.slug}`;
  }

  edit(server: McpServer): void {
    this.editingSlug = server.slug;
    this.form = {
      slug: server.slug,
      name: server.name,
      endpoint: server.endpoint,
      trust: server.trust,
    };
  }

  cancelEdit(): void {
    this.editingSlug = null;
    this.form = { slug: '', name: '', endpoint: '', trust: 'Needs review' };
  }

  save(): void {
    if (!this.form.slug || !this.form.name || !this.form.endpoint) return;

    this.saving = true;
    this.errorMessage = '';
    const obs = this.editingSlug
      ? this.api.updateServer(this.editingSlug, {
          name: this.form.name,
          endpoint: this.form.endpoint,
          trust: this.form.trust,
        })
      : this.api.addServer({
          slug: this.form.slug,
          name: this.form.name,
          endpoint: this.form.endpoint,
          trust: this.form.trust,
        });

    obs.subscribe({
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
