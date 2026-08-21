import { Component } from '@angular/core';

import { PolicyCodeComponent } from '../shared/policy-code.component';
import { PolicyRuleBuilderComponent } from '../shared/policy-rule-builder.component';
import { ToolPolicyMatrixComponent } from '../shared/tool-policy-matrix.component';

@Component({
  selector: 'app-policies',
  imports: [PolicyRuleBuilderComponent, PolicyCodeComponent, ToolPolicyMatrixComponent],
  templateUrl: './policies.component.html',
})
export class PoliciesComponent {}
