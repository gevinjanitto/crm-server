import { projectEntries, groupEntriesByYear, projectGroupYear } from './projectYears';

describe('projectYears', () => {
  test('finished projects use completion year, unfinished fall back to group_year', () => {
    expect(projectGroupYear({ group_year: '2024' })).toBe('2024');
  });

  test('project with maintenance appears in its completion year and in the maintenance year', () => {
    const entries = projectEntries([{ id: 'a', group_year: '2024', maintenance_year: '2026' }, { id: 'b', group_year: '2025' }]);
    const grouped = groupEntriesByYear(entries);
    expect(grouped.map(([y]) => y)).toEqual(['2026', '2025', '2024']);
    expect(grouped[0][1][0].is_maintenance_entry).toBe(true);
    expect(grouped[2][1][0].is_maintenance_entry).toBe(false);
  });
});
