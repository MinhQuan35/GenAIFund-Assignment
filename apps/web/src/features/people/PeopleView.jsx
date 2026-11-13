import { useEffect, useState } from 'react';

export default function PeopleView() {
  const [people, setPeople] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/api/v1/campaigns/people')
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || 'Could not load people.');
        return body;
      })
      .then(setPeople)
      .catch((requestError) => setError(requestError.message));
  }, []);

  return (
    <section className="data-view">
      <div className="data-view-heading"><div><p className="eyebrow">PROSPECTS</p><h2>People</h2><p>Candidates collected across your campaigns.</p></div><span className="count-label">{people.length} people</span></div>
      {error && <p className="form-message form-message-error">{error}</p>}
      {!error && !people.length && <p className="empty-copy">No candidates yet. Add candidates from a campaign to see them here.</p>}
      <div className="people-list">
        {people.map((person) => <article className="person-row" key={person.id}>
          <div className="person-main"><div className="person-avatar" aria-hidden="true">{(person.display_name || person.username).slice(0, 1).toUpperCase()}</div><div><a className="person-name" href={person.profile_url} target="_blank" rel="noreferrer">{person.display_name || `@${person.username}`}</a><span className="person-handle">@{person.username}{person.location ? ` · ${person.location}` : ''}</span></div></div>
          <p className="person-bio">{person.bio || 'No profile bio added.'}</p>
          <div className="person-campaigns">{person.campaigns.map((campaign) => <span className="campaign-tag" key={campaign.campaign_id}>{campaign.campaign_name}</span>)}</div>
          <div className="person-evidence">{person.evidence.slice(0, 2).map((item) => <a href={item.source_url} target="_blank" rel="noreferrer" key={item.id}>{item.source_type}: {item.excerpt}</a>)}</div>
        </article>)}
      </div>
    </section>
  );
}
