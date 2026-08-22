import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { NgClass } from '@angular/common';

import { ApiService } from '../api.service';
import { AppStateService } from '../app.state.service';

const POLL_INTERVAL_MS = 8_000;

@Component({
  selector: 'app-approvals',
  imports: [NgClass],
  templateUrl: './approvals.component.html',
})
export class ApprovalsComponent implements OnInit, OnDestroy {
  protected state = inject(AppStateService);
  private readonly api = inject(ApiService);

  errorMessage = '';
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    this.state.refreshApprovals();
    this.pollTimer = setInterval(() => this.state.refreshApprovals(), POLL_INTERVAL_MS);
  }

  ngOnDestroy(): void {
    if (this.pollTimer !== null) clearInterval(this.pollTimer);
  }

  approve(id: number): void {
    this.errorMessage = '';
    this.api.approveRequest(id).subscribe({
      next: () => this.state.refreshApprovals(),
      error: (err) => { this.errorMessage = err?.error?.detail ?? 'Failed to approve.'; },
    });
  }

  deny(id: number): void {
    this.errorMessage = '';
    this.api.denyRequest(id).subscribe({
      next: () => this.state.refreshApprovals(),
      error: (err) => { this.errorMessage = err?.error?.detail ?? 'Failed to deny.'; },
    });
  }

  argumentSummary(args: Record<string, unknown>): string {
    const keys = Object.keys(args);
    if (keys.length === 0) return '—';
    return keys.map((k) => `${k}: ${JSON.stringify(args[k])}`).join(', ');
  }
}
