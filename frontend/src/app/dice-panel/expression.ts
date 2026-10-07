export type GameSystem = 'dnd' | 'warhammer';

export interface GameConfig {
  label: string;
  /** Dice offered in the picker, from smallest to largest. */
  dice: readonly number[];
}

export const GAME_SYSTEMS: Record<GameSystem, GameConfig> = {
  dnd: { label: 'D&D', dice: [2, 4, 6, 8, 10, 12, 20, 100] },
  warhammer: { label: 'Warhammer 40K', dice: [3, 6] },
};

/** Warhammer "X+" targets for hit, wound and save rolls. */
export const SUCCESS_TARGETS = [2, 3, 4, 5, 6] as const;

export interface RollOptions {
  /** Warhammer: count d6 showing this value or more instead of summing them. */
  successOn?: number | null;
}

/**
 * Builds a dice expression understood by the backend, e.g. "1d20+3d6+2" or "10d6>=3".
 * Only the dice of the given game system are used.
 */
export function buildExpression(
  game: GameSystem,
  counts: Record<number, number>,
  modifier: number,
  options: RollOptions = {},
): string {
  const { successOn = null } = options;

  // A Warhammer test is a pool of d6 counted against a target; nothing else is added.
  if (game === 'warhammer' && successOn) {
    const count = counts[6] ?? 0;
    return count > 0 ? `${count}d6>=${successOn}` : '';
  }

  const terms: string[] = [];
  for (const sides of [...GAME_SYSTEMS[game].dice].reverse()) {
    const count = counts[sides] ?? 0;
    if (count > 0) terms.push(`${count}d${sides}`);
  }
  if (terms.length === 0) return '';

  let expression = terms.join('+');
  if (modifier > 0) expression += `+${modifier}`;
  if (modifier < 0) expression += `${modifier}`;
  return expression;
}
