import { Component, computed, inject } from '@angular/core';
import { RoomSocketService } from './core/room-socket.service';
import { SessionService } from './core/session.service';
import { Lobby } from './lobby/lobby';
import { Login } from './login/login';
import { RoomView } from './room/room';

@Component({
  selector: 'app-root',
  imports: [Login, Lobby, RoomView],
  templateUrl: './app.html',
})
export class App {
  protected readonly session = inject(SessionService);
  protected readonly socket = inject(RoomSocketService);

  protected readonly view = computed(() => {
    if (!this.session.username()) return 'login';
    return this.socket.state() === 'connected' ? 'room' : 'lobby';
  });

  protected logout(): void {
    this.socket.disconnect();
    this.session.logout();
  }
}
