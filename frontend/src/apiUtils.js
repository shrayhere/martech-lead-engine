// Adds ?run_id=... when a Smart Upload run is selected ('' = staged flow).
export const withRun = (url, runId) =>
  runId ? `${url}${url.includes('?') ? '&' : '?'}run_id=${encodeURIComponent(runId)}` : url;
