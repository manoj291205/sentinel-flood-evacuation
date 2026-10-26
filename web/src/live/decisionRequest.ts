export type DecisionIdentity = { session_id: string; state_version: number; recommendation_id: string };
export type DecisionIntent = {
  decision: 'ACCEPT' | 'OVERRIDE' | 'REJECT'; selected_action?: string; reason: string;
  evidence: { source_id: string; page: number; chunk_id: string };
};
export type PreparedDecision = DecisionIntent & { request_id: string; expected_state_version: number; recommendation_id: string };

export function prepareDecision(identity: DecisionIdentity, intent: DecisionIntent): PreparedDecision {
  if (!identity || !Number.isInteger(identity.state_version) || !/^[0-9a-f]{64}$/.test(identity.recommendation_id)) {
    throw new Error('A current server decision identity is required. Refresh the suggestion before deciding.');
  }
  return { ...intent, request_id: crypto.randomUUID(), expected_state_version: identity.state_version,
    recommendation_id: identity.recommendation_id };
}
