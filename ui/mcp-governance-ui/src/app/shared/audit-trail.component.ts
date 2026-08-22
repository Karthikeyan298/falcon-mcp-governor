import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { NgClass } from '@angular/common';

import { AppStateService } from '../app.state.service';

const POLL_INTERVAL_MS = 10_000;

@Component({
  selector: 'app-audit-trail',
  imports: [NgClass],
  templateUrl: './audit-trail.component.html',
  host: { class: 'panel' },
})
export class AuditTrailComponent implements OnInit, OnDestroy {
  protected state = inject(AppStateService);

  private pollTimer: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    this.state.refreshAudit();
    this.pollTimer = setInterval(() => this.state.refreshAudit(), POLL_INTERVAL_MS);
  }

  ngOnDestroy(): void {
    if (this.pollTimer !== null) {
      clearInterval(this.pollTimer);
    }
  }

  argsSummary(args: Record<string, unknown> | null): string {
    if (!args) return '—';
    const pairs = Object.entries(args).map(([k, v]) => {
      const s = typeof v === 'string' ? v : JSON.stringify(v);
      return `${k}=${s.length > 40 ? s.slice(0, 40) + '…' : s}`;
    });
    const joined = pairs.join(', ');
    return joined.length > 80 ? joined.slice(0, 80) + '…' : joined;
  }

  exportAuditLog(): void {
    const blob = new Blob([JSON.stringify(this.state.auditTrail, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'mcp-audit-log.json';
    anchor.click();
    URL.revokeObjectURL(url);
  }
}
