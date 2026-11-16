import { useEffect, useState } from 'react';

const emptyCampaign = { name: '', segment: '', seedAccounts: '' };
const emptyCandidate = {
  username: '', displayName: '', bio: '', location: '', fitReason: '', fitScore: '',
  sourceUrl: '', sourceType: 'profile', excerpt: '',
};

async function request(path, options) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

export default function CampaignWorkspace() {
  const [campaigns, setCampaigns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [campaignForm, setCampaignForm] = useState(emptyCampaign);
  const [candidateForm, setCandidateForm] = useState(emptyCandidate);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [saving, setSaving] = useState(false);
  const [draftingId, setDraftingId] = useState('');
  const [scoringId, setScoringId] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [targetUsers, setTargetUsers] = useState(20);
  const [removingId, setRemovingId] = useState('');
  const [clearingCandidates, setClearingCandidates] = useState(false);

  useEffect(() => {
    request('/api/v1/campaigns').then(setCampaigns).catch((error) => setMessage({ type: 'error', text: error.message }));
  }, []);

  async function createCampaign(event) {
    event.preventDefault();
    setSaving(true);
    setMessage({ type: '', text: '' });
    try {
      const campaign = await request('/api/v1/campaigns', {
        method: 'POST',
        body: JSON.stringify({
          name: campaignForm.name,
          segment: campaignForm.segment,
          seed_accounts: campaignForm.seedAccounts.split(',').map((item) => item.trim()).filter(Boolean),
        }),
      });
      setCampaigns((current) => [campaign, ...current]);
      setSelected({ ...campaign, candidates: [] });
      setCampaignForm(emptyCampaign);
      setMessage({ type: 'success', text: 'Campaign created.' });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setSaving(false);
    }
  }

  async function selectCampaign(campaignId) {
    try {
      setSelected(await request(`/api/v1/campaigns/${campaignId}`));
      setMessage({ type: '', text: '' });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    }
  }

  async function addCandidate(event) {
    event.preventDefault();
    if (!selected) return;
    setSaving(true);
    try {
      await request(`/api/v1/campaigns/${selected.id}/candidates`, {
        method: 'POST',
        body: JSON.stringify({
          username: candidateForm.username,
          display_name: candidateForm.displayName || null,
          bio: candidateForm.bio || null,
          location: candidateForm.location || null,
          fit_reason: candidateForm.fitReason,
          fit_score: candidateForm.fitScore === '' ? null : Number(candidateForm.fitScore),
          evidence: [{ source_url: candidateForm.sourceUrl, source_type: candidateForm.sourceType, excerpt: candidateForm.excerpt }],
        }),
      });
      setSelected(await request(`/api/v1/campaigns/${selected.id}`));
      setCandidateForm(emptyCandidate);
      setMessage({ type: 'success', text: 'Candidate and evidence saved.' });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setSaving(false);
    }
  }

  async function generateDraft(candidate) {
    setDraftingId(candidate.id);
    try {
      await request(`/api/v1/campaigns/${selected.id}/candidates/${candidate.id}/draft`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setSelected(await request(`/api/v1/campaigns/${selected.id}`));
      setMessage({ type: 'success', text: 'DM draft generated from the saved evidence.' });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setDraftingId('');
    }
  }

  async function scoreWithAI(candidate) {
    setScoringId(candidate.id);
    try {
      const scored = await request(`/api/v1/campaigns/${selected.id}/candidates/${candidate.id}/score`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setSelected(await request(`/api/v1/campaigns/${selected.id}`));
      const evidenceNote = scored.fit_assessment?.evidence_refresh === 'recent_posts_added'
        ? ' Pulled recent posts from X first.'
        : scored.fit_assessment?.evidence_refresh === 'x_posts_unavailable'
          ? ' X posts were unavailable, so it used saved evidence only.'
          : '';
      setMessage({ type: 'success', text: `Foundry scored @${candidate.username}.${evidenceNote}` });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setScoringId('');
    }
  }

  async function removeCandidate(candidate) {
    if (!selected) return;
    const hasOutreachHistory = ['send_pending', 'sent', 'replied'].includes(candidate.message?.status);
    const confirmed = window.confirm(
      hasOutreachHistory
        ? `Hide @${candidate.username} from this campaign? Sent messages and replies will stay in Conversations.`
        : `Remove @${candidate.username} and its unsent draft from this campaign?`,
    );
    if (!confirmed) return;
    setRemovingId(candidate.id);
    try {
      await request(`/api/v1/campaigns/${selected.id}/candidates/${candidate.id}`, { method: 'DELETE' });
      setSelected(await request(`/api/v1/campaigns/${selected.id}`));
      setMessage({ type: 'success', text: `@${candidate.username} removed from the campaign.` });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setRemovingId('');
    }
  }

  async function discoverCandidates() {
    if (!selected) return;
    setDiscovering(true);
    try {
      const result = await request(`/api/v1/campaigns/${selected.id}/discover`, {
        method: 'POST',
        body: JSON.stringify({ target_users: Number(targetUsers) }),
      });
      setSelected(await request(`/api/v1/campaigns/${selected.id}`));
      const reasonSummary = Object.entries(result.excluded_reasons || {})
        .map(([reason, count]) => `${reason} (${count})`)
        .join('; ');
      const filterNote = reasonSummary ? ` Reasons: ${reasonSummary}.` : '';
      setMessage({ type: 'success', text: `Saved ${result.saved} qualified candidates and filtered out ${result.excluded}.${filterNote} Search read ${result.pages_read} page(s) and checked ${result.timeline_profiles_checked}/${result.timeline_profile_limit} timelines.` });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setDiscovering(false);
    }
  }

  async function clearCandidates() {
    if (!selected) return;
    const confirmed = window.confirm('Remove all unsent candidates and drafts from this campaign? Candidates with sent or pending DMs will stay so outreach history is preserved.');
    if (!confirmed) return;
    setClearingCandidates(true);
    try {
      const result = await request(`/api/v1/campaigns/${selected.id}/candidates`, { method: 'DELETE' });
      setSelected(await request(`/api/v1/campaigns/${selected.id}`));
      setMessage({ type: 'success', text: `Removed ${result.removed} candidates. Kept ${result.preserved} with sent or pending DMs.` });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setClearingCandidates(false);
    }
  }

  return (
    <div className="campaign-layout">
      <section className="campaign-list-panel">
        <div className="section-heading section-heading-compact">
          <div><p className="eyebrow">OUTREACH</p><h2>Campaigns</h2></div>
          <span className="count-label">{campaigns.length}</span>
        </div>
        <form className="campaign-form" onSubmit={createCampaign}>
          <label>Name<input required value={campaignForm.name} onChange={(event) => setCampaignForm({ ...campaignForm, name: event.target.value })} placeholder="AI builders pilot" /></label>
          <label>Target segment<textarea required rows="2" value={campaignForm.segment} onChange={(event) => setCampaignForm({ ...campaignForm, segment: event.target.value })} placeholder="AI infrastructure founders in Southeast Asia" /></label>
          <label>Seed accounts <span className="field-hint">comma separated</span><input value={campaignForm.seedAccounts} onChange={(event) => setCampaignForm({ ...campaignForm, seedAccounts: event.target.value })} placeholder="username, another_account" /></label>
          <button className="primary-button form-button" disabled={saving} type="submit">Create campaign</button>
        </form>
        <div className="campaign-items">
          {campaigns.map((campaign) => <button key={campaign.id} className={`campaign-item ${selected?.id === campaign.id ? 'campaign-item-active' : ''}`} onClick={() => selectCampaign(campaign.id)} type="button"><strong>{campaign.name}</strong><span>{campaign.segment}</span></button>)}
          {!campaigns.length && <p className="empty-copy">Create your first campaign to begin.</p>}
        </div>
      </section>

      <section className="campaign-detail-panel">
        {selected ? (
          <>
            <div className="detail-header"><div><p className="eyebrow">CAMPAIGN · {selected.status.toUpperCase()}</p><h2>{selected.name}</h2><p>{selected.segment}</p></div><div className="detail-actions"><label className="target-count-label">Target users<input aria-label="Number of users to find" type="number" min="1" max="100" step="1" value={targetUsers} onChange={(event) => setTargetUsers(event.target.value)} disabled={discovering} /></label><span className="environment-label candidate-count-label">{selected.candidates.length} candidates</span><button className="primary-button" type="button" disabled={discovering || !targetUsers || Number(targetUsers) < 1 || Number(targetUsers) > 100} onClick={discoverCandidates}>{discovering ? 'Searching…' : 'Find on X'}</button><button className="secondary-button clear-candidates-button" type="button" disabled={clearingCandidates || !selected.candidates.length} onClick={clearCandidates}>{clearingCandidates ? 'Clearing…' : 'Clear candidates'}</button></div></div>
            <div className="candidate-grid">
              {selected.candidates.map((candidate) => (
                <article className="candidate-card" key={candidate.id}>
                  <div className="candidate-top">
                    <div><strong>@{candidate.username}</strong><span>{candidate.display_name || 'No display name'}</span></div>
                    <div className="candidate-tools">
                      <span className="score-label">{candidate.fit_score ?? '—'} / 100</span>
                      <button className="icon-button remove-candidate-button" type="button" aria-label={`Remove @${candidate.username} from campaign`} title={['send_pending', 'sent', 'replied'].includes(candidate.message?.status) ? 'Hide candidate; keep message history' : 'Remove candidate'} disabled={removingId === candidate.id} onClick={() => removeCandidate(candidate)}>×</button>
                    </div>
                  </div>
                  <p>{candidate.fit_reason}</p>
                  <div className={`qualification-state ${candidate.qualification?.eligible ? 'qualification-ready' : 'qualification-needs-work'}`}>
                    <strong>{candidate.qualification?.eligible ? 'Ready for AI score' : 'Needs more evidence'}</strong>
                    <span>
                      {candidate.qualification?.signals?.account_age_days != null
                        ? `${Math.floor(candidate.qualification.signals.account_age_days / 365)}y account`
                        : 'Account age unknown'}
                      {' · '}{candidate.qualification?.signals?.post_count ?? 0} relevant posts
                    </span>
                  </div>
                  {!candidate.qualification?.eligible && candidate.qualification?.missing?.length > 0 && (
                    <ul className="qualification-missing">
                      {candidate.qualification.missing.map((reason) => <li key={reason}>{reason}</li>)}
                    </ul>
                  )}
                  {candidate.fit_assessment && (
                    <div className="score-breakdown" aria-label="AI score breakdown">
                      <span className="score-method">AI assessment · Foundry</span>
                      {[
                        ['role_relevance', 'Role'],
                        ['domain_relevance', 'AI/robotics'],
                        ['region_relevance', 'Region'],
                      ].map(([key, label]) => (
                        <span className="score-dimension" key={key}>{label}<strong>{candidate.fit_assessment.dimensions?.[key]}</strong></span>
                      ))}
                      <span className="score-dimension">Confidence<strong>{candidate.fit_assessment.evidence_confidence}</strong></span>
                    </div>
                  )}
                  <div className="evidence-list">{candidate.evidence.map((item) => <a key={item.id} href={item.source_url} target="_blank" rel="noreferrer">{item.source_type}: {item.excerpt}</a>)}</div>
                  <div className="candidate-card-footer">
                    <span className="candidate-status">{candidate.message ? `Draft ${candidate.message.status}` : 'No DM draft yet'}</span>
                    <button className="secondary-button" type="button" disabled={!candidate.qualification?.eligible || scoringId === candidate.id || removingId === candidate.id} title="Requires a domain signal, a relevant role, and supporting evidence. Uses Foundry and may fetch X posts." onClick={() => scoreWithAI(candidate)}>{scoringId === candidate.id ? 'Scoring…' : !candidate.qualification?.eligible ? 'Add evidence first' : candidate.fit_assessment ? 'Re-score with AI' : 'Score with AI'}</button>
                    <button className="secondary-button" type="button" disabled={draftingId === candidate.id || candidate.message?.status === 'approved'} onClick={() => generateDraft(candidate)}>{draftingId === candidate.id ? 'Generating…' : candidate.message ? 'Regenerate draft' : 'Generate DM'}</button>
                  </div>
                </article>
              ))}
              {!selected.candidates.length && <p className="empty-copy">Add a candidate with a source excerpt to create an evidence-backed workspace.</p>}
            </div>
            <form className="candidate-form" onSubmit={addCandidate}><div className="form-section-heading"><p className="eyebrow">ADD CANDIDATE</p><span>Evidence is required</span></div><div className="form-grid"><label>Username<input required value={candidateForm.username} onChange={(event) => setCandidateForm({ ...candidateForm, username: event.target.value })} placeholder="username" /></label><label>Display name<input value={candidateForm.displayName} onChange={(event) => setCandidateForm({ ...candidateForm, displayName: event.target.value })} /></label><label>Fit score<input type="number" min="0" max="100" value={candidateForm.fitScore} onChange={(event) => setCandidateForm({ ...candidateForm, fitScore: event.target.value })} placeholder="0–100" /></label><label>Location<input value={candidateForm.location} onChange={(event) => setCandidateForm({ ...candidateForm, location: event.target.value })} /></label></div><label>Why do they fit?<textarea required rows="2" value={candidateForm.fitReason} onChange={(event) => setCandidateForm({ ...candidateForm, fitReason: event.target.value })} placeholder="Evidence-based reason for inclusion" /></label><div className="form-grid"><label>Source URL<input required type="url" value={candidateForm.sourceUrl} onChange={(event) => setCandidateForm({ ...candidateForm, sourceUrl: event.target.value })} placeholder="https://..." /></label><label>Source type<select value={candidateForm.sourceType} onChange={(event) => setCandidateForm({ ...candidateForm, sourceType: event.target.value })}><option value="profile">Profile</option><option value="post">Post</option><option value="website">Website</option><option value="other">Other</option></select></label></div><label>Evidence excerpt<textarea required rows="3" value={candidateForm.excerpt} onChange={(event) => setCandidateForm({ ...candidateForm, excerpt: event.target.value })} placeholder="Paste the relevant public evidence here" /></label><button className="primary-button form-button" disabled={saving} type="submit">Save candidate</button></form>
          </>
        ) : <div className="empty-state"><p className="eyebrow">WORKSPACE</p><h2>Select a campaign</h2><p>Campaign candidates, evidence and message drafts will appear here.</p></div>}
        {message.text && <div className={`form-message form-message-${message.type}`} role="status">{message.text}</div>}
      </section>
    </div>
  );
}
