import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { Player, Room } from './models';

const STORAGE_KEY = 'fiasco.username';

/** Username-only credentials, persisted in localStorage. */
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly http = inject(HttpClient);

  readonly username = signal<string | null>(localStorage.getItem(STORAGE_KEY));

  async login(username: string): Promise<Player> {
    const player = await firstValueFrom(this.http.post<Player>('/api/login', { username }));
    localStorage.setItem(STORAGE_KEY, player.username);
    this.username.set(player.username);
    return player;
  }

  logout(): void {
    localStorage.removeItem(STORAGE_KEY);
    this.username.set(null);
  }

  listRooms(): Promise<Room[]> {
    return firstValueFrom(this.http.get<Room[]>('/api/rooms'));
  }
}
