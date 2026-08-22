import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api.service';
import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-param-rule-builder',
  imports: [FormsModule],
  templateUrl: './param-rule-builder.component.html',
  host: { class: 'panel' },
})
export class ParamRuleBuilderComponent {
  protected state = inject(AppStateService);
  private readonly api = inject(ApiService);

  form = {
    agentScope: '',
    server: '',
    tool: '*',
    param: '',
    operator: 'equals',
    value: '',
    decision: 'deny',
    reason: '',
  };

  adding = false;
  errorMessage = '';

  readonly operators = [
    { value: 'equals',      label: 'equals' },
    { value: 'not_equals',  label: 'not equals' },
    { value: 'endswith',    label: 'ends with' },
    { value: 'not_endswith', label: 'does not end with' },
  ];

  readonly decisions = [
    { value: 'deny',             label: 'Deny' },
    { value: 'allow',            label: 'Allow' },
    { value: 'require_approval', label: 'Require approval' },
  ];

  toolsForServer(slug: string) {
    return this.state.toolsForServer(slug);
  }

  submit(): void {
    if (!this.form.server || !this.form.param || !this.form.value) return;
    this.adding = true;
    this.errorMessage = '';
    this.api.previewPolicyParamRule({
      yaml: this.state.policyYaml,
      agent: this.form.agentScope || null,
      server: this.form.server,
      tool: this.form.tool || '*',
      param: this.form.param,
      operator: this.form.operator,
      value: this.form.value,
      decision: this.form.decision,
      reason: this.form.reason,
    }).subscribe({
      next: (res) => {
        this.adding = false;
        this.state.policyYaml = res.yaml;
      },
      error: (err) => {
        this.adding = false;
        this.errorMessage = err?.error?.detail ?? 'Failed to build param rule.';
      },
    });
  }
}
