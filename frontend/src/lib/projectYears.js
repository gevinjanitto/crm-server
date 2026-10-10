import { isValid, parseISO } from 'date-fns';

export const projectStartYear = project => {
  const value = project.start_date;
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:$|T)/.test(value)) return 'undated';
  return isValid(parseISO(value.slice(0, 10))) ? value.slice(0, 4) : 'undated';
};

export const groupProjectsByStartYear = projects => {
  const groups = new Map();
  projects.forEach(project => {
    const year = projectStartYear(project);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(project);
  });
  return [...groups].sort(([a], [b]) => a === 'undated' ? 1 : b === 'undated' ? -1 : Number(b) - Number(a));
};