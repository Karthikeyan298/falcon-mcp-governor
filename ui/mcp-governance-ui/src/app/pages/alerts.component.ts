import { Component, inject, OnInit } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { Alert, AlertRules, ApiService } from '../api.service';
import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-alerts',
  imports: [NgClass, FormsModule],
  templateUrl: './alerts.component.html',
})
export class AlertsComponent implements OnInit {
  private readonly api = inject(ApiService);
  protected readonly state = inject(AppStateService);

  alerts: Alert[] = [];
  rules: AlertRules | null = null;
  showRules = false;
  savingRules = false;
  errorMessage = '';
  successMessage = '';

  readonly severityOptions = ['low', 'medium', 'high'] as const;

  readonly rulesMeta: { key: keyof AlertRules; label: string; hasWindow: boolean }[] = [
    { key: 'repeated_denials', label: 'Repeated denials', hasWindow: true },
    { key: 'high_call_rate',   label: 'High call rate',   hasWindow: true },
    { key: 'new_tool_attempt', label: 'New tool attempt',  hasWindow: false },
    { key: 'approval_flood',   label: 'Approval flood',    hasWindow: true },
  ];

  ngOnInit(): void {
    this.loadAlerts();
    this.loadRules();
  }

  loadAlerts(): void {
    this.api.getAlerts().subscribe({ next: (a) => (this.alerts = a), error: () => {} });
  }

  loadRules(): void {
    this.api.getAlertRules().subscribe({ next: (r) => (this.rules = r), error: () => {} });
  }

  acknowledge(id: number): void {
    this.api.acknowledgeAlert(id).subscribe({
      next: () => {
        this.loadAlerts();
        this.state.refreshAlertCount();
      },
      error: (err) => (this.errorMessage = err?.error?.detail ?? 'Failed to acknowledge alert.'),
    });
  }

  saveRules(): void {
    if (!this.rules) return;
    this.savingRules = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.api.updateAlertRules(this.rules).subscribe({
      next: () => {
        this.savingRules = false;
        this.successMessage = 'Detection rules saved.';
      },
      error: (err) => {
        this.savingRules = false;
        this.errorMessage = err?.error?.detail ?? 'Failed to save rules.';
      },
    });
  }

  unacknowledgedCount(): number {
    return this.alerts.filter((a) => !a.acknowledgedAt).length;
  }

  severityClass(severity: string): string {
    if (severity === 'high') return 'high';
    if (severity === 'medium') return 'medium';
    return 'low';
  }

  typeLabel(type: string): string {
    const labels: Record<string, string> = {
      repeated_denials: 'Repeated Denials',
      high_call_rate: 'High Call Rate',
      new_tool_attempt: 'New Tool Attempt',
      approval_flood: 'Approval Flood',
    };
    return labels[type] ?? type;
  }
}
