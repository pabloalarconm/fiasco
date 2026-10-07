import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { SessionService } from '../core/session.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  template: `
    <section class="card narrow">
      <h2>Login</h2>
      <p class="display">Enter the tavern</p>
      <p class="muted small">Pick a name. No password needed.</p>
      <form (ngSubmit)="submit()">
        <input
          name="username"
          [(ngModel)]="username"
          placeholder="Your adventurer name"
          maxlength="24"
          autofocus
          required
        />
        <button type="submit" [disabled]="busy() || username.trim().length < 2">Enter</button>
      </form>
      @if (error()) {
        <p class="error">[Error: {{ error() }}]</p>
      }
    </section>
  `,
})
export class Login {
  private readonly session = inject(SessionService);

  protected username = '';
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected async submit(): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.session.login(this.username.trim());
    } catch (err) {
      const detail = (err as HttpErrorResponse).error?.detail;
      this.error.set(Array.isArray(detail) ? detail[0].msg : 'Could not sign in');
    } finally {
      this.busy.set(false);
    }
  }
}
