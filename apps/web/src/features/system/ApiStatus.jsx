const labels = {
  loading: 'Checking API',
  online: 'API connected',
  offline: 'API unavailable',
};

export default function ApiStatus({ state }) {
  return (
    <div className={`api-status api-status-${state}`} role="status" aria-live="polite">
      <span className="status-dot" aria-hidden="true" />
      {labels[state]}
    </div>
  );
}
