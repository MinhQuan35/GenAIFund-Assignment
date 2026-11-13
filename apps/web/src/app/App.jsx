import { useEffect, useState } from 'react';
import ApiStatus from '../features/system/ApiStatus.jsx';

export default function App() {
  const [api, setApi] = useState({ state: 'loading', environment: null });
  const [services, setServices] = useState({ supabase: null, foundry: null });
  const [foundryCheck, setFoundryCheck] = useState({ state: 'idle', message: '' });

  useEffect(() => {
    const controller = new AbortController();

    fetch('/api/v1/health', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`API responded with ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setApi({ state: 'online', environment: data.environment });
        setServices(data.dependencies || {});
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setApi({ state: 'offline', environment: null });
      });

    return () => controller.abort();
  }, []);

  async function runFoundryCheck() {
    setFoundryCheck({ state: 'checking', message: 'Sending a short test request…' });
    try {
      const response = await fetch('/api/v1/integrations/foundry/check', { method: 'POST' });
      const result = await response.json();
      setFoundryCheck({ state: result.status, message: result.message });
      setServices((current) => ({ ...current, foundry: result }));
    } catch {
      setFoundryCheck({ state: 'error', message: 'Could not reach the backend.' });
    }
  }

  function serviceLabel(service) {
    if (!service) return 'Checking';
    return {
      connected: 'Connected',
      configured: 'Ready to check',
      not_configured: 'Needs setup',
      error: 'Unavailable',
    }[service.status] || 'Unknown';
  }

  function serviceState(service) {
    if (!service) return 'loading';
    if (service.status === 'connected') return 'online';
    if (service.status === 'error') return 'offline';
    return 'pending';
  }

  return (
    <div className="workspace">
      <aside className="sidebar" aria-label="Main navigation">
        <a className="brand" href="/" aria-label="GenAI Fund home">
          <span className="brand-mark" aria-hidden="true">G</span>
          <span>GenAI Fund</span>
        </a>
        <div className="nav-label">Workspace</div>
        <nav>
          <a className="nav-item nav-item-active" href="/" aria-current="page">
            <span className="nav-icon" aria-hidden="true">◫</span>
            Overview
          </a>
          <span className="nav-item nav-item-muted" aria-disabled="true">
            <span className="nav-icon" aria-hidden="true">◎</span>
            Campaigns
          </span>
          <span className="nav-item nav-item-muted" aria-disabled="true">
            <span className="nav-icon" aria-hidden="true">♙</span>
            People
          </span>
          <span className="nav-item nav-item-muted" aria-disabled="true">
            <span className="nav-icon" aria-hidden="true">↗</span>
            Conversations
          </span>
        </nav>
        <div className="sidebar-footer">
          <span className="account-dot" aria-hidden="true" />
          <span>Local workspace</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> Overview</div>
          <ApiStatus state={api.state} />
        </header>

        <section className="page-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">GENAI FUND · SOUTHEAST ASIA</p>
              <h1>Outreach workspace</h1>
              <p className="subtitle">Find relevant builders and keep every conversation organized.</p>
            </div>
            <button className="primary-button" type="button" disabled>
              <span aria-hidden="true">+</span> New campaign
            </button>
          </div>

          <section className="system-panel" aria-labelledby="system-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">SYSTEM</p>
                <h2 id="system-title">Project services</h2>
              </div>
              <span className="environment-label">
                {api.environment || 'Local development'}
              </span>
            </div>
            <div className="service-row">
              <div className="service-name">
                <span className={`status-dot status-${api.state}`} aria-hidden="true" />
                <div>
                  <strong>FastAPI backend</strong>
                  <span>Health endpoint</span>
                </div>
              </div>
              <span className={`service-state service-state-${api.state}`}>
                {api.state === 'loading' ? 'Checking' : api.state === 'online' ? 'Connected' : 'Unavailable'}
              </span>
            </div>
            <div className="service-row">
              <div className="service-name">
                <span className={`status-dot status-${serviceState(services.supabase)}`} aria-hidden="true" />
                <div>
                  <strong>Supabase</strong>
                  <span>{services.supabase?.message || 'Server connection check'}</span>
                </div>
              </div>
              <span className={`service-state service-state-${serviceState(services.supabase)}`}>
                {serviceLabel(services.supabase)}
              </span>
            </div>
            <div className="service-row service-row-last">
              <div className="service-name">
                <span className={`status-dot status-${serviceState(services.foundry)}`} aria-hidden="true" />
                <div>
                  <strong>Azure AI Foundry</strong>
                  <span>{foundryCheck.message || services.foundry?.message || 'Deployment connection check'}</span>
                </div>
              </div>
              <div className="service-actions">
                <span className={`service-state service-state-${serviceState(services.foundry)}`}>
                  {foundryCheck.state === 'checking' ? 'Checking' : serviceLabel(services.foundry)}
                </span>
                <button className="secondary-button" type="button" onClick={runFoundryCheck} disabled={foundryCheck.state === 'checking'}>
                  Check Foundry
                </button>
              </div>
            </div>
          </section>

          <div className="bottom-note">
            <span className="note-rule" />
            <p>Campaigns and contacts will appear here as you build your workspace.</p>
          </div>
        </section>
      </main>
    </div>
  );
}
