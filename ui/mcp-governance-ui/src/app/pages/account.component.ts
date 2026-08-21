import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from '../api.service';
import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-account',
  imports: [FormsModule],
  templateUrl: './account.component.html',
})
export class AccountComponent {
  protected state = inject(AppStateService);
  private api = inject(ApiService);
  private router = inject(Router);

  form = { currentPassword: '', newPassword: '', confirmPassword: '' };
  changing = false;
  successMessage = '';
  errorMessage = '';

  changePassword(): void {
    if (this.form.newPassword !== this.form.confirmPassword) {
      this.errorMessage = 'New passwords do not match.';
      return;
    }
    this.changing = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.api.changePassword(this.form.currentPassword, this.form.newPassword).subscribe({
      next: () => {
        this.changing = false;
        this.successMessage = 'Password changed successfully.';
        this.form = { currentPassword: '', newPassword: '', confirmPassword: '' };
      },
      error: (err) => {
        this.changing = false;
        this.errorMessage = err?.error?.detail ?? 'Failed to change password.';
      },
    });
  }

  logout(): void {
    this.api.logout().subscribe({
      next: () => {
        this.state.currentUser = null;
        this.router.navigate(['/login']);
      },
      error: () => {
        this.state.currentUser = null;
        this.router.navigate(['/login']);
      },
    });
  }
}
