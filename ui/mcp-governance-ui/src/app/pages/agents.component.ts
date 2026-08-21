import { Component, inject } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api.service';
import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-agents',
  imports: [NgClass, FormsModule],
  templateUrl: './agents.component.html',
})
export class AgentsComponent {
  protected state = inject(AppStateService);
  private api = inject(ApiService);

  form = { name: '', owner: '', environment: 'Production', tools_allowed: 0 };
  registering = false;
  newApiKey: { name: string; key: string } | null = null;
  errorMessage = '';

  register(): void {
    if (!this.form.name || !this.form.owner) return;
    this.registering = true;
    this.errorMessage = '';
    this.api.registerAgent({ ...this.form, status: 'Active' }).subscribe({
      next: (created) => {
        this.registering = false;
        this.newApiKey = { name: created.name, key: created.api_key };
        this.form = { name: '', owner: '', environment: 'Production', tools_allowed: 0 };
        this.state.refreshAll();
      },
      error: (err) => {
        this.registering = false;
        this.errorMessage = err?.error?.detail ?? 'Failed to register agent.';
      },
    });
  }

  dismissKey(): void {
    this.newApiKey = null;
  }

  toggleStatus(name: string): void {
    this.api.toggleAgent(name).subscribe({
      next: () => this.state.refreshAll(),
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to update agent status.';
      },
    });
  }

  remove(name: string): void {
    if (!confirm(`Remove agent "${name}"?`)) return;
    this.api.removeAgent(name).subscribe({
      next: () => this.state.refreshAll(),
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to remove agent.';
      },
    });
  }
}
