import { Component, computed, input } from '@angular/core';
import { RollResult, RollTerm } from '../core/models';

interface DieView {
  value: number;
  kept: boolean;
  outcome: 'max' | 'min' | null;
}

@Component({
  selector: 'app-roll-card',
  template: `
    <div class="roll-card" [class.crit]="critical() === 'success'" [class.fumble]="critical() === 'failure'">
      <div class="roll-head">
        <code>{{ result().expression }}</code>
        <span class="total"
          >{{ result().total }}
          @if (countsSuccesses()) {
            <span class="unit">{{ result().total === 1 ? 'success' : 'successes' }}</span>
          }
        </span>
      </div>
      <div class="roll-terms">
        @for (term of result().terms; track $index) {
          <span class="term">
            @if ($index > 0 || term.sign < 0) {
              <span class="op">{{ term.sign < 0 ? '−' : '+' }}</span>
            }
            @if (term.rolls.length) {
              <span class="muted">{{ term.label }}</span>
              @for (die of dice(term); track $index) {
                <span
                  class="die"
                  [class.dropped]="!die.kept"
                  [class.max]="die.outcome === 'max'"
                  [class.min]="die.outcome === 'min'"
                  >{{ die.value }}</span
                >
              }
            } @else {
              <span class="flat">{{ term.label }}</span>
            }
          </span>
        }
      </div>
      @if (critical() === 'success') {
        <div class="badge">Natural 20</div>
      } @else if (critical() === 'failure') {
        <div class="badge">Natural 1</div>
      }
    </div>
  `,
})
export class RollCard {
  readonly result = input.required<RollResult>();

  /** True when the total is a number of successes ("NdM>=T") rather than a sum. */
  protected readonly countsSuccesses = computed(() => this.result().terms.some((t) => t.target != null));

  /** Natural 20 / 1 when the roll contains exactly one kept d20. */
  protected readonly critical = computed(() => {
    const d20 = this.result().terms.filter((t) => /d20(k[hl]\d+)?$/.test(t.label));
    if (d20.length !== 1 || d20[0].kept.length !== 1) return null;
    const value = d20[0].kept[0];
    return value === 20 ? 'success' : value === 1 ? 'failure' : null;
  });

  /** Marks which rolled dice were kept (handling duplicates) and which hit their max/min face. */
  protected dice(term: RollTerm): DieView[] {
    const remaining = [...term.kept];
    return term.rolls.map((value) => {
      const idx = remaining.indexOf(value);
      if (idx >= 0) remaining.splice(idx, 1);
      const outcome = value === term.sides ? 'max' : value === 1 ? 'min' : null;
      return { value, kept: idx >= 0, outcome };
    });
  }
}
