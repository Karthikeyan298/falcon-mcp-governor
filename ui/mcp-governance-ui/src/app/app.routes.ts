import { Routes } from '@angular/router';

import { OverviewComponent } from './pages/overview.component';
import { AgentsComponent } from './pages/agents.component';
import { ServersComponent } from './pages/servers.component';
import { PoliciesComponent } from './pages/policies.component';
import { GatewayComponent } from './pages/gateway.component';
import { AuditComponent } from './pages/audit.component';
import { AccountComponent } from './pages/account.component';
import { UsersComponent } from './pages/users.component';
import { AlertsComponent } from './pages/alerts.component';
import { ApprovalsComponent } from './pages/approvals.component';

export const routes: Routes = [
  { path: '', redirectTo: 'overview', pathMatch: 'full' },
  { path: 'overview', component: OverviewComponent },
  { path: 'agents', component: AgentsComponent },
  { path: 'servers', component: ServersComponent },
  { path: 'policies', component: PoliciesComponent },
  { path: 'gateway', component: GatewayComponent },
  { path: 'audit', component: AuditComponent },
  { path: 'account', component: AccountComponent },
  { path: 'users', component: UsersComponent },
  { path: 'alerts', component: AlertsComponent },
  { path: 'approvals', component: ApprovalsComponent },
];
