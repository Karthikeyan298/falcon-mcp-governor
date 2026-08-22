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
  private readonly api = inject(ApiService);

  form = { agentScope: '', server: '', tool: '*', action: 'allow' };
  addingRule = false;
  errorMessage = '';

  paramForm = {
    agentScope: '', server: '', tool: '', param: '',
    operator: 'equals', value: '', decision: 'deny', reason: '',
  };
  addingParamRule = false;
  paramErrorMessage = '';

  readonly operators = [
    { value: 'equals', label: 'equals' },
    { value: 'not_equals', label: 'not equals' },
    { value: 'contains', label: 'contains' },
    { value: 'not_contains', label: 'not contains' },
    { value: 'startswith', label: 'starts with' },
    { value: 'not_startswith', label: 'not starts with' },
    { value: 'endswith', label: 'ends with' },
    { value: 'not_endswith', label: 'not ends with' },
  ];

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

  submitParamRule(): void {
    if (!this.paramForm.server || !this.paramForm.tool || !this.paramForm.param || !this.paramForm.value) return;
    this.addingParamRule = true;
    this.paramErrorMessage = '';
    this.api
      .previewPolicyParamRule({
        yaml: this.state.policyYaml,
        agent: this.paramForm.agentScope || null,
        server: this.paramForm.server,
        tool: this.paramForm.tool,
        param: this.paramForm.param,
        operator: this.paramForm.operator,
        value: this.paramForm.value,
        decision: this.paramForm.decision,
        reason: this.paramForm.reason,
      })
      .subscribe({
        next: (res) => {
          this.addingParamRule = false;
          this.state.policyYaml = res.yaml;
        },
        error: (err) => {
          this.addingParamRule = false;
          this.paramErrorMessage = err?.error?.detail ?? 'Failed to build parameter rule.';
        },
      });
  }
}
