import { Injectable, signal } from '@angular/core';
import { FeedEntry, JoinMode, Player, ServerMessage } from './models';

export type ConnectionState = 'idle' | 'connecting' | 'connected' | 'closed';

/** Manages the WebSocket connection to a single room and exposes its state as signals. */
@Injectable({ providedIn: 'root' })
export class RoomSocketService {
  private socket: WebSocket | null = null;

  readonly state = signal<ConnectionState>('idle');
  readonly room = signal<string | null>(null);
  readonly players = signal<Player[]>([]);
  readonly feed = signal<FeedEntry[]>([]);
  readonly error = signal<string | null>(null);

  connect(room: string, username: string, mode: JoinMode): void {
    this.disconnect();
    this.error.set(null);
    this.feed.set([]);
    this.players.set([]);
    this.state.set('connecting');

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const params = new URLSearchParams({ room, username, mode });
    const socket = new WebSocket(`${protocol}://${location.host}/ws?${params}`);
    this.socket = socket;

    socket.onmessage = (event) => this.handle(JSON.parse(event.data) as ServerMessage);
    socket.onclose = (event) => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.state.set('closed');
      if (event.code !== 1000 && !this.error()) {
        this.error.set(event.reason || 'Connection lost');
      }
    };
  }

  disconnect(): void {
    if (this.socket) {
      const socket = this.socket;
      this.socket = null;
      socket.close(1000);
    }
    this.state.set('idle');
    this.room.set(null);
  }

  sendChat(text: string): void {
    this.send({ type: 'chat', text });
  }

  roll(expression: string): void {
    this.send({ type: 'roll', expression });
  }

  private send(payload: object): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  private handle(msg: ServerMessage): void {
    switch (msg.type) {
      case 'welcome':
        this.room.set(msg.room);
        this.players.set(msg.players);
        this.feed.set(msg.history);
        this.state.set('connected');
        break;
      case 'players':
        this.players.set(msg.players);
        break;
      case 'error':
        this.error.set(msg.message);
        break;
      default:
        this.feed.update((feed) => [...feed, msg]);
    }
  }
}
