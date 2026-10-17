import type { Ack, Certificate, DecisionWhy, DemoState, EvidenceResponse, MapGeometry, RuleTiersResponse, SystemStatus } from './types';

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

const post = (body?: object): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body ?? {}),
});

export const api = {
  geometry: () => json<MapGeometry>('/api/map/geometry'),
  demoState: () => json<DemoState>('/api/demo/state'),
  demoStart: () => json<DemoState>('/api/demo/start', post()),
  demoStep: (action: 'next' | 'prev' | 'reset') => json<DemoState>('/api/demo/step', post({ action })),
  certificates: () => json<{ certificates: Certificate[] }>('/api/certificates'),
  sessionCertificates: (id: string) => json<{ certificates: Certificate[] }>(`/api/sessions/${encodeURIComponent(id)}/certificates`),
  sessionReplay: (id: string, cert: string, tamper: boolean) => json<{ result: 'MATCH' | 'MISMATCH'; mismatched_fields: string[] }>(`/api/sessions/${encodeURIComponent(id)}/certificates/${encodeURIComponent(cert)}/replay`, post({ tamper })),
  certificate: (id: string) => json<Certificate>(`/api/certificates/${encodeURIComponent(id)}`),
  replay: (id: string, tamper: boolean) => json<{ result: 'MATCH' | 'MISMATCH'; mismatched_fields: string[] }>(`/api/certificates/${encodeURIComponent(id)}/replay`, post({ tamper })),
  why: (id: string) => json<DecisionWhy>(`/api/decisions/${encodeURIComponent(id)}/why`),
  evidence: () => json<EvidenceResponse>('/api/evidence'),
  ruleTiers: () => json<RuleTiersResponse>('/api/constraints/tiers'),
  systemStatus: () => json<SystemStatus>('/api/system/status'),
  systemAcks: () => json<{ items: Ack[] }>('/api/system/acks'),
};
