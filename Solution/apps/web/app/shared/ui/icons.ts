const svg = (path: string) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`
export const workspaceIcons = {
  bin: svg('<path d="m6 7 1 14h10l1-14Z" fill="currentColor" fill-opacity=".14"/><path d="M4 7h16M9 3h6l1 4M10 11v6m4-6v6"/>'),
  calendar: svg('<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 11h18m-12 5h2"/>'),
  chevronLeft: svg('<path d="m15 6-6 6 6 6"/>'),
  chevronRight: svg('<path d="m9 6 6 6-6 6"/>'),
  search: svg('<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>'),
  arrowRight: svg('<path d="M4 12h16m-6-6 6 6-6 6"/>'),

  chevronUp: svg('<path d="m6 15 6-6 6 6"/>'),
  chevronDown: svg('<path d="m6 9 6 6 6-6"/>'),
  planning: svg('<circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="M6 7v8a4 4 0 0 0 8 0V9a4 4 0 0 1 8 0v4"/>'),
  history: svg('<path d="M4 7h16M9 3h6l1 4M6 7l1 14h10l1-14M10 11v6M14 11v6"/>'),
  analytics: svg('<path d="M4 20V4m0 16h17M8 16v-4m5 4V6m5 10V9"/>'),
  forecasts: svg('<path d="M4 20V4m0 16h17M7 15l4-5 4 3 6-8"/>'),
  manifest: svg('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M9 9h6M9 13h6M9 17h4"/>'),
  status: svg('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3m6 0h4"/>'),
  recycling: svg('<path d="m8 7 3-5 4 7m-3-1 3 1 1-3m3 5 3 5-8 1m2-3-2 3 2 2M10 19H3l4-7m0 3v-3H4"/>'),
  lock: svg('<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>'),
}
