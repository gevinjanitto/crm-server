export const PROJECT_LIST_ROLES = ['Admin', 'Admin Project', 'Developer', 'Accounting'];
export const canListProjects = user => PROJECT_LIST_ROLES.includes(user?.role);