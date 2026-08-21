import { Component, inject } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { ApiService, GatewayInvokeResult, Tool } from '../api.service';
import { AppStateService } from '../app.state.service';
import { AuditTrailComponent } from '../shared/audit-trail.component';

interface ParamField {
  name: string;
  type: string;
  required: boolean;
  isJson: boolean;
}

@Component({
  selector: 'app-gateway',
  imports: [NgClass, FormsModule, AuditTrailComponent],
  templateUrl: './gateway.component.html',
})
export class GatewayComponent {
  protected state = inject(AppStateService);
  private api = inject(ApiService);

  form = { agent: '', server: '', tool: '', user: '' };
  paramValues: Record<string, string> = {};
  result: GatewayInvokeResult | null = null;
  invoking = false;
  errorMessage = '';

  toolsForServer(slug: string): Tool[] {
    return this.state.toolsForServer(slug);
  }

  onServerChange(): void {
    const first = this.toolsForServer(this.form.server)[0];
    this.form.tool = first?.name ?? '';
    this.paramValues = {};
  }

  onToolChange(): void {
    this.paramValues = {};
  }

  private selectedTool(): Tool | undefined {
    return this.toolsForServer(this.form.server).find((t) => t.name === this.form.tool);
  }

  paramFields(): ParamField[] {
    const schema = this.selectedTool()?.inputSchema;
    const properties = schema?.properties ?? {};
    const required = new Set(schema?.required ?? []);
    return Object.keys(properties).map((name) => {
      const type = properties[name].type ?? 'string';
      return { name, type, required: required.has(name), isJson: type === 'object' || type === 'array' };
    });
  }

  submit(): void {
    if (!this.form.agent || !this.form.server || !this.form.tool || !this.form.user) return;

    const params: Record<string, unknown> = {};
    for (const field of this.paramFields()) {
      const raw = this.paramValues[field.name];
      if (raw === undefined || raw === '') continue;
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
    this.result = null;
    this.errorMessage = '';
    this.api.invokeGateway({ ...this.form, params }).subscribe({
      next: (res) => {
        this.result = res;
        this.invoking = false;
        this.state.refreshAll();
      },
      error: (err) => {
        this.invoking = false;
        this.errorMessage = err?.error?.detail ?? 'Gateway invocation failed.';
      },
    });
  }
}
