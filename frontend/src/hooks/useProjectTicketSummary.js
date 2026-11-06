import useSWR from 'swr';
import { api } from '../lib/api';

export const useProjectTicketSummary = (projectId, role) => {
  const allowed = ['Admin', 'Admin Project', 'Developer', 'Client'].includes(role);
  return useSWR(allowed && projectId ? `/projects/${projectId}/tickets/summary` : null,
    path => api.get(path).then(response => response.data),
    { refreshInterval: 30000, revalidateOnFocus: true, shouldRetryOnError: false });
};