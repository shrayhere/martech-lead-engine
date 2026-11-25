// Adds ?run_id=... when a Smart Upload run is selected ('' = staged flow).
export const withRun = (url, runId) =>
  runId ? `${url}${url.includes('?') ? '&' : '?'}run_id=${encodeURIComponent(runId)}` : url;

// Set up automatic authentication header & 401 handling
if (typeof window !== 'undefined' && !window._authFetchPatched) {
  const originalFetch = window.fetch;
  window.fetch = async (...args) => {
    let [resource, config] = args;
    config = config ? { ...config } : {};

    // Ensure cookies are sent with requests (httpOnly session cookie)
    config.credentials = config.credentials || 'include';

    const response = await originalFetch(resource, config);

    // If 401 received on a non-auth endpoint, broadcast unauthorized event
    if (response.status === 401) {
      const urlStr = typeof resource === 'string' ? resource : resource?.url || '';
      if (!urlStr.includes('/api/auth/login') && !urlStr.includes('/api/auth/status')) {
        window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      }
    }

    return response;
  };
  window._authFetchPatched = true;
}
