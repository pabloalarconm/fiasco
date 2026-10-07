import { Component, ElementRef, effect, inject, viewChild } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RoomSocketService } from '../core/room-socket.service';
import { SessionService } from '../core/session.service';
import { DicePanel } from '../dice-panel/dice-panel';
import { RollCard } from '../roll-card/roll-card';

@Component({
  selector: 'app-room',
  imports: [FormsModule, DatePipe, DicePanel, RollCard],
  template: `
    <div class="room-header">
      <div>
        <span class="label">Room</span>
        <p class="display">{{ socket.room() }}</p>
      </div>
      <button class="ghost" (click)="socket.disconnect()">Leave room</button>
    </div>

    @if (socket.error(); as error) {
      <p class="error banner" (click)="socket.error.set(null)">[Error: {{ error }}]</p>
    }

    <div class="room-layout">
      <aside class="card players">
        <h2>Players · {{ socket.players().length }}</h2>
        <ul>
          @for (player of socket.players(); track player.id) {
            <li [class.me]="player.username === session.username()">
              <span class="dot"></span>{{ player.username }}
            </li>
          }
        </ul>
      </aside>

      <section class="card chat">
        <div class="feed" #feed>
          @for (entry of socket.feed(); track $index) {
            @switch (entry.type) {
              @case ('system') {
                <div class="entry system">{{ entry.text }}</div>
              }
              @case ('chat') {
                <div class="entry" [class.mine]="entry.username === session.username()">
                  <div class="meta">{{ entry.username }} · {{ entry.created_at | date: 'HH:mm' }}</div>
                  <div class="bubble">{{ entry.text }}</div>
                </div>
              }
              @case ('roll') {
                <div class="entry" [class.mine]="entry.username === session.username()">
                  <div class="meta">{{ entry.username }} rolled · {{ entry.created_at | date: 'HH:mm' }}</div>
                  <app-roll-card [result]="entry.result" />
                </div>
              }
            }
          }
        </div>
        <form class="row composer" (ngSubmit)="send()">
          <input name="message" [(ngModel)]="message" placeholder="Say something…" maxlength="500" autocomplete="off" />
          <button type="submit" [disabled]="!message.trim()">Send</button>
        </form>
      </section>

      <app-dice-panel (roll)="socket.roll($event)" />
    </div>
  `,
})
export class RoomView {
  protected readonly socket = inject(RoomSocketService);
  protected readonly session = inject(SessionService);
  private readonly feedEl = viewChild<ElementRef<HTMLElement>>('feed');

  protected message = '';

  constructor() {
    // Keep the feed scrolled to the newest entry.
    effect(() => {
      this.socket.feed();
      const el = this.feedEl()?.nativeElement;
      if (el) setTimeout(() => (el.scrollTop = el.scrollHeight));
    });
  }

  protected send(): void {
    this.socket.sendChat(this.message.trim());
    this.message = '';
  }
}
