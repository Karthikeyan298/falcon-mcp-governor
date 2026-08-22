import { Component, inject, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { FormsModule } from '@angular/forms';

import { ApiService } from './api.service';
import { AppStateService } from './app.state.service';

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  protected state = inject(AppStateService);
  private readonly api = inject(ApiService);

  loginForm = { username: '', password: '' };
  loginError = '';
  loggingIn = false;

  readonly navItems = [
    { label: 'Overview', path: '/overview' },
    { label: 'Agents', path: '/agents' },
    { label: 'Servers', path: '/servers' },
    { label: 'Policies', path: '/policies' },
    { label: 'Gateway', path: '/gateway' },
    { label: 'Audit', path: '/audit' },
    { label: 'Approvals', path: '/approvals' },
    { label: 'Alerts', path: '/alerts' },
    { label: 'Account', path: '/account' },
  ];

  readonly adminNavItem = { label: 'Users', path: '/users' };

  visibleNavItems() {
    return this.state.currentUser?.role === 'admin'
      ? [...this.navItems, this.adminNavItem]
      : this.navItems;
  }

  ngOnInit(): void {
    this.state.init();
  }

  login(): void {
    if (!this.loginForm.username || !this.loginForm.password) return;
    this.loggingIn = true;
    this.loginError = '';
    this.api.login(this.loginForm.username, this.loginForm.password).subscribe({
      next: (user) => {
        this.loggingIn = false;
        this.loginForm = { username: '', password: '' };
        this.state.afterLogin(user);
      },
      error: (err) => {
        this.loggingIn = false;
        this.loginError = err?.error?.detail ?? 'Login failed.';
      },
    });
  }
}
