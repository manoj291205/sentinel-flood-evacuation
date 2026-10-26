import { describe, expect, it } from 'vitest';
import { committedDecisionCount, episodeOutcomeLabel, subjectSentence, toFeedItem, type OperatorEntry } from './sessionStore';

describe('live session presentation', () => {
  it('turns each WebSocket message into a readable, linked feed item', () => {
    const cases = [
      [{ type: 'decision', payload: { timestep: 2, decision: 'OVERRIDE' } }, 'OVERRIDE recorded', 'ok'],
      [{ type: 'certificate', payload: { cert_id: 'CERT-000002', kind: 'DISPATCH' } }, 'CERT-000002 issued', 'ok'],
      [{ type: 'recheck', payload: { group_id: 'G-1', action: 'MIGRATE', cert_id: 'CERT-000003' } }, 'Re-routed automatically', 'info'],
      [{ type: 'event', payload: { event_type: 'ROUTE_CLOSED' } }, 'ROUTE_CLOSED', 'info'],
      [{ type: 'refusal', payload: { action_key: 'Z1->S2', verdict: 'UNDECIDED' } }, 'Gate refused', 'danger'],
      [{ type: 'state', payload: { current_timestep: 3 } }, 'State updated', 'info'],
    ] as const;
    for (const [message, words, tone] of cases) {
      const item = toFeedItem(message, 'session-one');
      expect(item.text).toContain(words);
      expect(item.tone).toBe(tone);
      expect(item.text).not.toContain('{');
      expect(toFeedItem(message, 'session-one')).toEqual(item);
    }
    expect(toFeedItem(cases[1][0], 'session-one').href).toBe('/decisions?session=session-one&cert=CERT-000002');
  });

  it('shows unavailable subject fields without inventing a route or ETA', () => {
    expect(subjectSentence({ action_key: 'WAIT', kind: 'HOLD', people: null, zone_id: null, shelter_id: null })).toBe('HOLD: no dispatch this step');
    expect(subjectSentence({ action_key: 'Z1->S2', kind: 'DISPATCH', people: 20, zone_id: 'Z1', shelter_id: 'S2' })).toContain('road travel estimate —');
    expect(subjectSentence({ action_key: 'Z1->S2', kind: 'DISPATCH', people: 20, zone_id: 'Z1', shelter_id: 'S2', eta_minutes: .48541 })).toContain('road travel estimate 0.49 min');
  });

  it('counts committed operator decisions separately from refusals and migrations', () => {
    const entries = ['ACCEPT', 'OVERRIDE', 'REFUSED', 'AUTO_REROUTE', 'DECLINE'].map(decision =>
      ({ decision, source: 'LIVE' }) as OperatorEntry);
    expect(committedDecisionCount(entries)).toBe(3);
    expect(committedDecisionCount([...entries, { decision: 'ACCEPT', source: 'PRACTICE' } as OperatorEntry])).toBe(3);
  });

  it('never presents failed or horizon-limited outcomes as a successful evacuation', () => {
    expect(episodeOutcomeLabel('ALL_FAILED')).toContain('failed');
    expect(episodeOutcomeLabel('MIXED_OUTCOME')).toContain('mixed');
    expect(episodeOutcomeLabel('HORIZON_REACHED')).toContain('horizon');
    expect(episodeOutcomeLabel('ALL_EVACUATED')).toContain('arrived safely');
  });
});
