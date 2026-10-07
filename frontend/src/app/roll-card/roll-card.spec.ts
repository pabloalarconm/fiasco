import { TestBed } from '@angular/core/testing';
import { RollCard } from './roll-card';

describe('RollCard', () => {
  it('marks dice that hit their maximum in green and minimum in red', () => {
    const fixture = TestBed.createComponent(RollCard);
    fixture.componentRef.setInput('result', {
      expression: '3d6+2',
      total: 11,
      terms: [
        { sign: 1, label: '3d6', sides: 6, rolls: [6, 1, 2], kept: [6, 1, 2], subtotal: 9 },
        { sign: 1, label: '2', sides: null, rolls: [], kept: [], subtotal: 2 },
      ],
    });
    fixture.detectChanges();

    const dice = [...(fixture.nativeElement as HTMLElement).querySelectorAll('.die')];
    expect(dice.map((d) => d.className.replace('die', '').trim())).toEqual(['max', 'min', '']);
  });

  it('labels success counts and strikes through the dice that missed the target', () => {
    const fixture = TestBed.createComponent(RollCard);
    fixture.componentRef.setInput('result', {
      expression: '3d6>=4',
      total: 2,
      terms: [{ sign: 1, label: '3d6>=4', sides: 6, rolls: [5, 2, 4], kept: [5, 4], target: 4, subtotal: 2 }],
    });
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.total')?.textContent).toContain('successes');
    const dropped = [...el.querySelectorAll('.die.dropped')].map((d) => d.textContent);
    expect(dropped).toEqual(['2']);
  });
});
