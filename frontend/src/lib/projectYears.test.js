import { groupProjectsByStartYear, projectStartYear } from './projectYears';

describe('projectYears', () => {
  test('projectStartYear uses calendar year from valid ISO date', () => {
    expect(projectStartYear({ start_date: '2026-01-02' })).toBe('2026');
    expect(projectStartYear({ start_date: '2025-12-31T23:59:59+07:00' })).toBe('2025');
    expect(projectStartYear({ start_date: '2024-07-01T00:00:00Z' })).toBe('2024');
  });

  test('projectStartYear returns undated for null/missing/invalid', () => {
    expect(projectStartYear({ start_date: null })).toBe('undated');
    expect(projectStartYear({})).toBe('undated');
    expect(projectStartYear({ start_date: 'not-a-date' })).toBe('undated');
    expect(projectStartYear({ start_date: '07/01/2026' })).toBe('undated');
  });

  test('groupProjectsByStartYear sorts newest first and undated last', () => {
    const grouped = groupProjectsByStartYear([
      { id: 'a', start_date: '2024-03-10' },
      { id: 'b', start_date: '2026-03-10T10:00:00Z' },
      { id: 'c', start_date: null },
      { id: 'd', start_date: '2025-03-10' },
      { id: 'e', start_date: 'bad-date' },
    ]);

    expect(grouped.map(([year]) => year)).toEqual(['2026', '2025', '2024', 'undated']);
    expect(grouped.find(([year]) => year === 'undated')[1].map(item => item.id)).toEqual(['c', 'e']);
  });
});
