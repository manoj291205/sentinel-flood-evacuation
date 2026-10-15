import type { DemoState, MapGeometry } from './types';

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
};
