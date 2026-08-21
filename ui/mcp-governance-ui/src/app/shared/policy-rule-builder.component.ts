import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api.service';
import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-policy-rule-builder',
  imports: [FormsModule],
  templateUrl: './policy-rule-builder.component.html',
  host: { class: 'panel' },
})
export class PolicyRuleBuilderComponent {
  protected state = inject(AppStateService);
  private api = inject(ApiService);

  form = { agentScope: '', server: '', tool: '*', action: 'allow' };
  addingRule = false;
  errorMessage = '';

  toolsForServer(slug: string) {
    return this.state.toolsForServer(slug);
  }

  submit(): void {
    if (!this.form.server) return;
    this.addingRule = true;
    this.errorMessage = '';
    this.api
      .previewPolicyRule({
        yaml: this.state.policyYaml,
        agent: this.form.agentScope || null,
        server: this.form.server,
        tool: this.form.tool || '*',
        action: this.form.action,
      })
      .subscribe({
        next: (res) => {
          this.addingRule = false;
          this.state.policyYaml = res.yaml;
        },
        error: (err) => {
          this.addingRule = false;
          this.errorMessage = err?.error?.detail ?? 'Failed to build policy rule.';
        },
      });
  }
}
