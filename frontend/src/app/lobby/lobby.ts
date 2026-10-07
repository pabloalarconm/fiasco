import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { JoinMode, Room } from '../core/models';
import { RoomSocketService } from '../core/room-socket.service';
import { SessionService } from '../core/session.service';

const REFRESH_MS = 3000;

@Component({
  selector: 'app-lobby',
  imports: [FormsModule, DatePipe],
  template: `
    @if (socket.error(); as error) {
      <p class="error banner">[Error: {{ error }}]</p>
    }

    <div class="lobby">
      <section class="card">
        <h2>Create a room</h2>
        <form (ngSubmit)="enter(newRoom.trim(), 'create')">
          <input name="room" [(ngModel)]="newRoom" placeholder="Room name" maxlength="24" required />
          <button type="submit" [disabled]="busy() || newRoom.trim().length < 2">Create</button>
        </form>

        <h3>Join by name</h3>
        <form (ngSubmit)="enter(joinRoom.trim(), 'join')">
          <input name="join" [(ngModel)]="joinRoom" placeholder="Existing room name" maxlength="24" />
          <button type="submit" [disabled]="busy() || joinRoom.trim().length < 2">Join</button>
        </form>
      </section>

      <section class="card">
        <h2>Open rooms</h2>
        @for (room of rooms(); track room.id) {
          <div class="room-row">
            <div>
              <div class="room-name">{{ room.name }}</div>
              <div class="label room-meta">
                {{ room.player_count }} player{{ room.player_count === 1 ? '' : 's' }}
                · by {{ room.created_by }} · {{ room.created_at | date: 'HH:mm' }}
              </div>
            </div>
            <button (click)="enter(room.name, 'join')" [disabled]="busy()">Join</button>
          </div>
        } @empty {
          <div class="empty">
            <p class="muted">No open rooms</p>
            <p class="label">Create the first one</p>
          </div>
        }
      </section>
    </div>
  `,
})
export class Lobby implements OnInit, OnDestroy {
  private readonly session = inject(SessionService);
  protected readonly socket = inject(RoomSocketService);

  protected newRoom = '';
  protected joinRoom = '';
  protected readonly rooms = signal<Room[]>([]);
  protected readonly busy = signal(false);
  private timer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.refresh();
    this.timer = setInterval(() => this.refresh(), REFRESH_MS);
  }

  ngOnDestroy(): void {
    clearInterval(this.timer);
  }

  protected enter(room: string, mode: JoinMode): void {
    const username = this.session.username();
    if (!username || !room) return;
    this.socket.connect(room, username, mode);
  }

  private async refresh(): Promise<void> {
    try {
      this.rooms.set(await this.session.listRooms());
    } catch {
      // Backend unreachable: keep the last known list.
    }
  }
}
