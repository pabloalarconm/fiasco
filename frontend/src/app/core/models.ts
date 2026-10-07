export interface Player {
  id: number;
  username: string;
  joined_at?: string;
}

export interface Room {
  id: number;
  name: string;
  created_by: string;
  created_at: string;
  player_count: number;
}

export interface RollTerm {
  sign: number;
  label: string;
  /** Number of faces; null for flat modifiers. */
  sides: number | null;
  rolls: number[];
  kept: number[];
  /** Success target for "NdM>=T" terms: kept holds the dice that met it. Missing in old rolls. */
  target?: number | null;
  subtotal: number;
}

export interface RollResult {
  expression: string;
  terms: RollTerm[];
  total: number;
}

export type FeedEntry =
  | { type: 'chat'; username: string; text: string; created_at: string }
  | { type: 'system'; text: string; created_at: string }
  | { type: 'roll'; username: string; result: RollResult; created_at: string };

export type ServerMessage =
  | FeedEntry
  | { type: 'welcome'; room: string; username: string; history: FeedEntry[]; players: Player[] }
  | { type: 'players'; players: Player[] }
  | { type: 'error'; message: string };

export type JoinMode = 'join' | 'create';
