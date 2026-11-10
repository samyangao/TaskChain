// Apply the saved theme before the stylesheet paints, avoiding a flash.
try {
  if (localStorage.getItem('taskchain-theme') === 'light') {
    document.documentElement.dataset.theme = 'light';
  }
} catch (e) { /* storage may be disabled */ }
