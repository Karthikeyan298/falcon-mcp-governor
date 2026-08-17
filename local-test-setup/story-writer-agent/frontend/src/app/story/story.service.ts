import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface StoryRequest {
  title: string;
  recipient_email: string;
}

export interface StoryResponse {
  title: string;
  story: string;
  db_status: string;
  db_tool_used: string | null;
  email_status: string;
  email_tool_used: string | null;
}

@Injectable({ providedIn: 'root' })
export class StoryService {
  constructor(private http: HttpClient) {}

  createStory(request: StoryRequest): Observable<StoryResponse> {
    return this.http.post<StoryResponse>(`${environment.apiBaseUrl}/stories`, request);
  }
}
