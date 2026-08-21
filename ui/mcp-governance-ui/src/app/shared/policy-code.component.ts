import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api.service';
import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-policy-code',
  imports: [FormsModule],
  templateUrl: './policy-code.component.html',
  host: { class: 'panel' },
})
export class PolicyCodeComponent {
  protected state = inject(AppStateService);
  private api = inject(ApiService);

  errorMessage = '';

  deploy(): void {
    this.errorMessage = '';
    this.api.deployPolicy(this.state.policyYaml).subscribe({
      next: () => this.state.refreshAll(),
      error: (err) => {
        this.errorMessage = err?.error?.detail ?? 'Failed to deploy policy: invalid YAML.';
      },
    });
  }
}
