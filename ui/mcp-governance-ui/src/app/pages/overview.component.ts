import { Component, inject } from '@angular/core';

import { AppStateService } from '../app.state.service';
import { AuditTrailComponent } from '../shared/audit-trail.component';
import { ToolPolicyMatrixComponent } from '../shared/tool-policy-matrix.component';

@Component({
  selector: 'app-overview',
  imports: [ToolPolicyMatrixComponent, AuditTrailComponent],
  templateUrl: './overview.component.html',
})
export class OverviewComponent {
  protected state = inject(AppStateService);
}
