import { Component, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { StoryService, StoryResponse } from './story/story.service';

@Component({
  selector: 'app-root',
  imports: [ReactiveFormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<StoryResponse | null>(null);

  protected readonly form;

  constructor(
    private fb: FormBuilder,
    private storyService: StoryService,
  ) {
    this.form = this.fb.group({
      title: ['', [Validators.required, Validators.minLength(2)]],
      recipientEmail: ['', [Validators.required, Validators.email]],
    });
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading.set(true);
    this.error.set(null);
    this.result.set(null);

    const { title, recipientEmail } = this.form.getRawValue();

    this.storyService
      .createStory({ title: title!, recipient_email: recipientEmail! })
      .subscribe({
        next: (response) => {
          this.result.set(response);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Something went wrong. Please try again.');
          this.loading.set(false);
        },
      });
  }
}
