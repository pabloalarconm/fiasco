import { buildExpression } from './expression';

describe('buildExpression', () => {
  it('returns an empty string when no dice are selected', () => {
    expect(buildExpression('dnd', {}, 5)).toBe('');
  });

  it('combines dice from largest to smallest with a modifier', () => {
    expect(buildExpression('dnd', { 6: 2, 20: 1 }, 3)).toBe('1d20+2d6+3');
    expect(buildExpression('dnd', { 8: 1 }, -2)).toBe('1d8-2');
  });

  it('only uses the dice of the selected game', () => {
    expect(buildExpression('dnd', { 3: 2, 20: 1, 2: 1 }, 0)).toBe('1d20+1d2');
    expect(buildExpression('warhammer', { 3: 1, 6: 2, 20: 1 }, 1)).toBe('2d6+1d3+1');
  });

  it('turns a Warhammer d6 pool into a success test', () => {
    expect(buildExpression('warhammer', { 6: 10, 3: 1 }, 2, { successOn: 3 })).toBe('10d6>=3');
    expect(buildExpression('warhammer', { 3: 1 }, 0, { successOn: 4 })).toBe('');
  });
});
