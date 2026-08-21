import { Component } from '@angular/core';

import { AuditTrailComponent } from '../shared/audit-trail.component';

@Component({
  selector: 'app-audit',
  imports: [AuditTrailComponent],
  template: `
    <section class="content-grid">
      <app-audit-trail class="span-3"></app-audit-trail>
    </section>
  `,
})
export class AuditComponent {}
