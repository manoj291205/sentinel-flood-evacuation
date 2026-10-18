export const SPEEDS = [1, 2, 3, 5, 10] as const;
export type Speed = typeof SPEEDS[number];
export default function SpeedControl({ speed, onChange }: { speed: Speed; onChange: (speed: Speed) => void }) {
  return <div role="group" aria-label="Playback speed">{SPEEDS.map(item => <button key={item} type="button" aria-pressed={speed === item} onClick={() => onChange(item)}>{item}×</button>)}</div>;
}
