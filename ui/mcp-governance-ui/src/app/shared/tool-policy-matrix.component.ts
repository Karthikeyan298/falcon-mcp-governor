import { Component, inject, OnInit } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { ApiService, ToolMatrixRow } from '../api.service';
import { AppStateService } from '../app.state.service';

@Component({
  selector: 'app-tool-policy-matrix',
  imports: [NgClass, FormsModule],
  templateUrl: './tool-policy-matrix.component.html',
  host: { class: 'panel' },
})
export class ToolPolicyMatrixComponent implements OnInit {
  protected state = inject(AppStateService);
  private readonly api = inject(ApiService);

  filterAgent = '';
  filterServer = '';
  private allRows: ToolMatrixRow[] = [];
  loading = false;

  ngOnInit(): void {
    this.loadMatrix();
  }

  get filteredRows(): ToolMatrixRow[] {
    return this.allRows.filter(
      (r) => (!this.filterServer || r.serverSlug === this.filterServer),
    );
  }

  onAgentChange(): void {
    this.filterServer = '';
    this.loadMatrix();
  }

  get uniqueServers(): { slug: string; name: string }[] {
    const seen = new Map<string, string>();
    for (const r of this.allRows) seen.set(r.serverSlug, r.server);
    return [...seen.entries()].map(([slug, name]) => ({ slug, name }));
  }

  private loadMatrix(): void {
    this.loading = true;
    this.api.getToolMatrix(this.filterAgent || undefined).subscribe({
      next: (rows) => { this.allRows = rows; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }
}
