import { useEffect, useState } from 'react';

async function apiRequest(path, options) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

export default function ConversationsView() {
  const [messages, setMessages] = useState([]);
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');
  const [syncing, setSyncing] = useState(false);

  async function refresh() {
    try {
      setMessages(await apiRequest('/api/v1/conversations'));
      setError('');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function saveContent(item, content) {
    setBusyId(item.id);
    try {
      const saved = await apiRequest(`/api/v1/messages/${item.id}`, { method: 'PATCH', body: JSON.stringify({ content }) });
      setMessages((current) => current.map((message) => message.id === item.id ? { ...message, ...saved } : message));
      setError('');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyId('');
    }
  }

  async function review(item, action) {
    setBusyId(item.id);
    try {
      const updated = await apiRequest(`/api/v1/messages/${item.id}/review`, { method: 'POST', body: JSON.stringify({ action }) });
      setMessages((current) => current.map((message) => message.id === item.id ? { ...message, ...updated } : message));
      setError('');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyId('');
    }
  }

  async function send(item) {
    const confirmation = window.confirm('Confirm that this recipient is your test account or has explicitly agreed to receive a test DM. Send this approved message?');
    if (!confirmation) return;
    setBusyId(item.id);
    try {
      const updated = await sendRequest(`/api/v1/messages/${item.id}/send`, { method: 'POST', body: JSON.stringify({ recipient_confirmed: true }) });
      setMessages((current) => current.map((message) => message.id === item.id ? { ...message, ...updated } : message));
      setError('');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyId('');
    }
  }

  async function syncReplies() {
    setSyncing(true);
    try {
      await sendRequest('/api/v1/conversations/sync', { method: 'POST', body: JSON.stringify({}) });
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSyncing(false);
    }
  }

  const filtered = filter === 'all' ? messages : messages.filter((item) => item.status === filter);

  return (
    <section className="data-view">
      <div className="data-view-heading"><div><p className="eyebrow">MESSAGE REVIEW</p><h2>Conversations</h2><p>Review generated messages before any sending integration is enabled.</p></div><span className="count-label">{messages.length} drafts</span></div>
      <div className="view-toolbar"><div className="segmented-control" aria-label="Filter conversations">{['all', 'draft', 'approved', 'sent', 'replied', 'rejected'].map((value) => <button type="button" className={filter === value ? 'segment-active' : ''} onClick={() => setFilter(value)} key={value}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div><div className="toolbar-actions"><button className="secondary-button" type="button" disabled={syncing} onClick={syncReplies}>{syncing ? 'Syncing…' : 'Sync replies'}</button><button className="secondary-button" type="button" onClick={refresh}>Refresh</button></div></div>
      {error && <p className="form-message form-message-error">{error}</p>}
      {!error && !filtered.length && <p className="empty-copy">No messages match this view.</p>}
      <div className="conversation-list">
        {filtered.map((item) => <MessageCard key={item.id} item={item} busy={busyId === item.id} onSave={saveContent} onReview={review} onSend={send} />)}
      </div>
    </section>
  );
}

function MessageCard({ item, busy, onSave, onReview, onSend }) {
  const [content, setContent] = useState(item.content);
  const candidate = item.candidate;
  return (
    <article className="conversation-item">
      <header className="conversation-header"><div><strong>{candidate?.display_name || `@${candidate?.username || 'unknown'}`}</strong><span>{item.campaign_name} · {candidate ? `@${candidate.username}` : ''}</span></div><span className={`message-status message-status-${item.status}`}>{item.status}</span></header>
      <textarea aria-label="Message draft" rows="4" value={content} onChange={(event) => setContent(event.target.value)} disabled={item.status !== 'draft' || busy} />
      <footer className="conversation-actions"><span>{content.length} characters</span><div>{item.status === 'draft' && <><button type="button" className="secondary-button" disabled={busy || content === item.content} onClick={() => onSave(item, content)}>Save edit</button><button type="button" className="secondary-button button-reject" disabled={busy} onClick={() => onReview(item, 'reject')}>Reject</button><button type="button" className="primary-button button-approve" disabled={busy} onClick={() => onReview(item, 'approve')}>Approve</button></>}{item.status === 'approved' && <button type="button" className="primary-button button-approve" disabled={busy} onClick={() => onSend(item)}>Send DM</button>}</div></footer>
      {item.status === 'approved' && <p className="approval-note">Only send to your test account or a recipient who agreed to the test.</p>}
      {item.status === 'sent' && <p className="approval-note">Sent {item.sent_at ? new Date(item.sent_at).toLocaleString() : ''}. Use Sync replies to check for a response.</p>}
      {item.interactions?.map((interaction) => <p className="reply-note" key={interaction.id}>{interaction.text || 'Reply received'} · {new Date(interaction.occurred_at).toLocaleString()}</p>)}
    </article>
  );
}

async function sendRequest(path, options) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}
