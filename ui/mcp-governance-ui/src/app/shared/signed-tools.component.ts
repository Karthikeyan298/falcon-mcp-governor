import { Component, inject } from '@angular/core';
import { NgClass } from '@angular/common';
import { Router } from '@angular/router';

import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-signed-tools',
  imports: [NgClass],
  templateUrl: './signed-tools.component.html',
  host: { class: 'panel' },
})
export class SignedToolsComponent {
  protected state = inject(AppStateService);
  private router = inject(Router);

  goToPolicies(): void {
    this.router.navigate(['/policies']);
  }
}
