import { Component, computed, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { GAME_SYSTEMS, GameSystem, SUCCESS_TARGETS, buildExpression } from './expression';

interface SyntaxRule {
  syntax: string;
  meaning: string;
  examples: string[];
}

const SYNTAX_RULES: SyntaxRule[] = [
  { syntax: 'NdM', meaning: 'Roll N dice with M sides (N defaults to 1)', examples: ['d20', '3d6'] },
  { syntax: '+ / -', meaning: 'Add or subtract dice and flat numbers', examples: ['1d20+5', '1d20+1d4-1'] },
  { syntax: 'khK', meaning: 'Keep the highest K dice', examples: ['2d20kh1', '4d6kh3'] },
  { syntax: 'klK', meaning: 'Keep the lowest K dice', examples: ['2d20kl1'] },
  { syntax: '>=T', meaning: 'Count dice showing T or more (successes)', examples: ['10d6>=3', '5d6>=4'] },
];

@Component({
  selector: 'app-dice-panel',
  imports: [FormsModule],
  template: `
    <section class="card dice-panel">
      <h2>Dice</h2>

      <div class="segmented" role="radiogroup" aria-label="Game">
        @for (system of gameSystems; track system.id) {
          <button
            type="button"
            role="radio"
            [class.active]="game() === system.id"
            [attr.aria-checked]="game() === system.id"
            (click)="setGame(system.id)"
          >
            {{ system.label }}
          </button>
        }
      </div>

      <p class="muted small">Click to add a die, right-click to remove one.</p>

      <div class="dice-grid">
        @for (sides of dice(); track sides) {
          <button
            class="dice-btn"
            [class.selected]="counts()[sides]"
            [disabled]="isTest() && sides !== 6"
            (click)="add(sides)"
            (contextmenu)="remove(sides, $event)"
          >
            <span class="dice-name">d{{ sides }}</span>
            @if (counts()[sides]; as count) {
              <span class="count">×{{ count }}</span>
            }
          </button>
        }
      </div>

      <div class="row">
        <label>
          Modifier
          <input
            type="number"
            [ngModel]="modifier()"
            (ngModelChange)="modifier.set(+$event || 0)"
            [disabled]="isTest()"
          />
        </label>
        @if (game() === 'warhammer') {
          <label>
            Roll type
            <select [ngModel]="successOn()" (ngModelChange)="setSuccessOn($event)">
              <option [ngValue]="null">Sum</option>
              @for (target of successTargets; track target) {
                <option [ngValue]="target">Test {{ target }}+</option>
              }
            </select>
          </label>
        }
      </div>
      @if (game() === 'warhammer') {
        <p class="muted small hint">
          @if (isTest()) {
            Counts the d6 that roll {{ successOn() }} or more: hits, wounds and saves.
          } @else {
            Adds the dice up: damage, charges, random attacks. Pick a test to count successes.
          }
        </p>
      }

      <div class="expression">
        <code>{{ expression() || '—' }}</code>
        <button class="ghost" (click)="clear()" [disabled]="!expression()">Clear</button>
      </div>
      <button class="primary wide" (click)="rollSelected()" [disabled]="!expression()">Roll</button>

      <h3>Custom expression</h3>
      <form class="row" (ngSubmit)="rollCustom()">
        <input name="custom" [(ngModel)]="custom" placeholder="e.g. 4d6kh3+2" maxlength="100" />
        <button type="submit" [disabled]="!custom.trim()">Roll</button>
      </form>
      <details class="syntax-help">
        <summary>Syntax help</summary>
        <table>
          @for (rule of syntaxRules; track rule.syntax) {
            <tr>
              <td><code>{{ rule.syntax }}</code></td>
              <td>
                {{ rule.meaning }}
                <div class="examples">
                  @for (example of rule.examples; track example) {
                    <button type="button" class="example" (click)="custom = example">{{ example }}</button>
                  }
                </div>
              </td>
            </tr>
          }
        </table>
        <p class="muted small">
          Up to 100 dice per term, 2 to 1000 sides, 20 terms and 100 characters. Spaces and case are ignored.
          Click an example to use it.
        </p>
      </details>
    </section>
  `,
})
export class DicePanel {
  readonly roll = output<string>();

  protected readonly gameSystems = Object.entries(GAME_SYSTEMS).map(([id, config]) => ({ id: id as GameSystem, ...config }));
  protected readonly successTargets = SUCCESS_TARGETS;
  protected readonly syntaxRules = SYNTAX_RULES;

  protected readonly game = signal<GameSystem>('dnd');
  protected readonly counts = signal<Record<number, number>>({});
  protected readonly modifier = signal(0);
  protected readonly successOn = signal<number | null>(null);
  protected custom = '';

  protected readonly dice = computed(() => GAME_SYSTEMS[this.game()].dice);
  protected readonly isTest = computed(() => this.game() === 'warhammer' && this.successOn() !== null);

  protected readonly expression = computed(() =>
    buildExpression(this.game(), this.counts(), this.modifier(), { successOn: this.successOn() }),
  );

  protected setGame(game: GameSystem): void {
    this.game.set(game);
    this.clear();
  }

  protected setSuccessOn(target: number | null): void {
    this.successOn.set(target);
    if (target !== null) {
      // A test only rolls d6, without a flat modifier.
      this.counts.update((c) => ({ 6: c[6] ?? 0 }));
      this.modifier.set(0);
    }
  }

  protected add(sides: number): void {
    this.counts.update((c) => ({ ...c, [sides]: Math.min((c[sides] ?? 0) + 1, 100) }));
  }

  protected remove(sides: number, event: Event): void {
    event.preventDefault();
    this.counts.update((c) => ({ ...c, [sides]: Math.max((c[sides] ?? 0) - 1, 0) }));
  }

  protected clear(): void {
    this.counts.set({});
    this.modifier.set(0);
    this.successOn.set(null);
  }

  protected rollSelected(): void {
    this.roll.emit(this.expression());
  }

  protected rollCustom(): void {
    this.roll.emit(this.custom.trim());
  }
}
