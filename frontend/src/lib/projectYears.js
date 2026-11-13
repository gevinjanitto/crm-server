export const currentYear = () => String(new Date().getFullYear());

// Finished projects sit in their deadline year, others in their start year (group_year from backend).
export const projectGroupYear = project => project.group_year || currentYear();

// One row per project in its own year, plus a maintenance row in the latest approved maintenance year.
export const projectEntries = projects => projects.flatMap(p => [
  { ...p, entry_key: `${p.id}-project`, entry_year: projectGroupYear(p), is_maintenance_entry: false },
  ...(p.maintenance_year ? [{ ...p, entry_key: `${p.id}-maintenance`, entry_year: p.maintenance_year, is_maintenance_entry: true }] : []),
]);

export const entryYears = projects => projectEntries(projects).map(e => e.entry_year);

export const sortYears = years => [...new Set(years)].sort((a, b) => Number(b) - Number(a));

export const yearLabel = year => year;

export const groupEntriesByYear = entries => {
  const groups = new Map();
  entries.forEach(e => {
    if (!groups.has(e.entry_year)) groups.set(e.entry_year, []);
    groups.get(e.entry_year).push(e);
  });
  return [...groups].sort(([a], [b]) => Number(b) - Number(a));
};
