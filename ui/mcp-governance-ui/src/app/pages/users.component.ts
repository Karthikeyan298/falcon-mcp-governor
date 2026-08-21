import { Component, inject } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api.service';
import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-users',
  imports: [NgClass, FormsModule],
  templateUrl: './users.component.html',
})
export class UsersComponent {
  protected state = inject(AppStateService);
  private api = inject(ApiService);

  form = { username: '', role: 'user' };
  creating = false;
  newUserCreated: { username: string; password: string } | null = null;
  errorMessage = '';

  create(): void {
    if (!this.form.username) return;
    this.creating = true;
    this.errorMessage = '';
    this.api.createUser(this.form).subscribe({
      next: (created) => {
        this.creating = false;
        this.newUserCreated = { username: created.username, password: created.temp_password };
        this.form = { username: '', role: 'user' };
        this.state.loadUsers();
      },
      error: (err) => {
        this.creating = false;
        this.errorMessage = err?.error?.detail ?? 'Failed to create user.';
      },
    });
  }

  dismissNewUser(): void {
    this.newUserCreated = null;
  }
}
