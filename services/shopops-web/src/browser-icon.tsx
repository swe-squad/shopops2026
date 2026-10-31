const paths = {
  back: 'm14 6-6 6 6 6M8 12h12',
  forward: 'm10 6 6 6-6 6M16 12H4',
  reload: 'M20 7v5h-5M20 12a8 8 0 1 0-2.3 5.7M20 7l-2.3-2.3',
  home: 'm3 10 9-7 9 7M5 9v11h5v-6h4v6h5V9',
  plus: 'M12 5v14M5 12h14',
  close: 'm6 6 12 12M6 18 18 6',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  external: 'M14 3h7v7m0-7L10 14M10 3H4v17h17v-6',
  lock: 'M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5zM12 14v3',
  globe: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  check: 'm5 12 4 4L19 6',
} as const

export function BrowserIcon({ name }: { name: keyof typeof paths }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
