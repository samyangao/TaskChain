// ==========================================
// 1. STATE & CONFIGURATION
// ==========================================
const state = {
  user: null,
  page: location.pathname === '/admin/security' ? 'monitor' : 'dashboard',
  tasks: [],
  users: [],
  notifications: [],
  allTasksForWorkload: null,
  notifUnread: null,
  notifLatest: null,
  notifTimer: null
};
