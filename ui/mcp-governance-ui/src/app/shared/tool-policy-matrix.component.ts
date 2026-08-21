import { Component, inject } from '@angular/core';
import { NgClass } from '@angular/common';
import { Router } from '@angular/router';

import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-tool-policy-matrix',
  imports: [NgClass],
  templateUrl: './tool-policy-matrix.component.html',
  host: { class: 'panel' },
})
export class ToolPolicyMatrixComponent {
  protected state = inject(AppStateService);
  private router = inject(Router);

  goToPolicies(): void {
    this.router.navigate(['/policies']);
  }
}
