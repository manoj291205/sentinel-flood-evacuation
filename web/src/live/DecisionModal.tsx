import { useEffect, useRef, useState } from 'react';
import styles from './DecisionModal.module.css';
import type { Subject, OperatorEntry } from './sessionStore';
import { subjectOf, subjectSentence } from './sessionStore';

export type Candidate = { action_key: string; label: string; verdict: string; lower: number | null; certified: boolean; comparison: string; subject?: Subject };
export type Recheck = { group_id: string; route: string; action: string; lower: number | null; cert_id: string | null };
export type Context = { certified: { timestep: number; recommendation: Candidate; why: string[]; alternatives: Candidate[]; rechecks: Recheck[]; note: string; threshold?: number; futures_used?: number; looks?: number } };
export type Decision = { audit_record: { decision: string }; certificates: { cert_id: string; kind: string }[]; rechecks: Recheck[] };
export type Refusal = { timestep: number; action_key: string; verdict: string | null; reason: string; flag: string };
type Choice = 'ACCEPT' | 'OVERRIDE' | 'REJECT';
const CODES = ['Local knowledge', 'Road report', 'Shelter report', 'Resource constraint', 'Other'];
function signedDelta(value: number | null) { return value == null ? '—' : `${value >= 0 ? '+' : ''}${value}`; }

export default function DecisionModal({ context, result, refusal, busy, session, safeDelta, onSubmit, onNext, initialChoice = 'ACCEPT', onClose, onPreview, requireCode = true, resultEntry }: {
  context: Context; result: Decision | null; refusal: Refusal | null; busy: boolean; session: string;
  safeDelta: number | null;
  onSubmit: (choice: Choice, selected: string, reason: string) => void; onNext: () => void;
  initialChoice?: Choice; onClose?: () => void; onPreview?: (key: string) => void; requireCode?: boolean; resultEntry?: OperatorEntry;
}) {
  const [minimised, setMinimised] = useState(false);
  const [choice, setChoice] = useState<Choice>(initialChoice);
  const [selected, setSelected] = useState('WAIT');
  const [code, setCode] = useState(requireCode && onClose ? '' : CODES[0]);
  const [reason, setReason] = useState('');
  const dialog = useRef<HTMLDivElement>(null);
  const submitRef = useRef(onSubmit);
  submitRef.current = onSubmit;
  useEffect(() => { setMinimised(false); setChoice(initialChoice); setSelected(context.certified.alternatives.find(row => row.certified)?.action_key ?? context.certified.alternatives[0]?.action_key ?? 'WAIT'); setCode(requireCode && onClose ? '' : CODES[0]); setReason(''); }, [context, initialChoice, requireCode]);
  useEffect(() => {
    if (minimised) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = dialog.current;
    node?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); if (onClose) onClose(); else setMinimised(true); return; }
      if (event.key === 'Tab' && node) {
        const all = [...node.querySelectorAll<HTMLElement>('button:not(:disabled),select:not(:disabled),input:not(:disabled),a[href]')];
        const first = all[0], last = all.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
      if (result || busy || event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return;
      const key = event.key.toLowerCase();
      if (key === 'a') { event.preventDefault(); submitRef.current('ACCEPT', '', ''); }
      else if (key === 'o') { event.preventDefault(); setChoice('OVERRIDE'); }
      else if (key === 'd') { event.preventDefault(); setChoice('REJECT'); }
    };
    document.addEventListener('keydown', keydown);
    return () => { document.removeEventListener('keydown', keydown); previous?.focus(); };
  }, [minimised, result, busy, onClose]);
  if (minimised) return <button type="button" className={styles.restore} onClick={() => setMinimised(false)}>Decision pending · open</button>;
  const pending = context.certified;
  const hold = pending.recommendation.action_key === 'WAIT';
  return <div className={styles.backdrop}><div ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="decision-title" className={styles.dialog}>
    <header className={styles.header}><div><small>OPERATOR DECISION · STEP {pending.timestep}</small><h2 id="decision-title">Decision for step {pending.timestep} · Suggested: {hold ? `HOLD: no dispatch this step — ${(pending.why[0] ?? 'no certified dispatch').replace('No dispatch option reached the threshold', 'No dispatch cleared the safety threshold')}` : subjectSentence(subjectOf(pending.recommendation))}</h2></div><span className={hold ? styles.hold : styles.certified}>{hold ? 'HOLD' : 'CERTIFIED'}</span><button type="button" onClick={() => onClose ? onClose() : setMinimised(true)} aria-label="Minimise decision">×</button></header>
    {refusal && <div className={styles.refusal} role="alert">Gate refused: not certified (verdict {refusal.verdict ?? 'unavailable'}). {refusal.flag}. The proposed route was not committed.</div>}
    {result ? <section className={styles.result}><h3>Decision recorded · {result.audit_record.decision === 'REJECT' ? 'DECLINE' : result.audit_record.decision}</h3><p>{resultEntry ? subjectSentence(resultEntry.subject) : subjectSentence(subjectOf(pending.recommendation))}{resultEntry?.alternative ? ` (instead of ${subjectSentence(resultEntry.alternative)})` : ''}</p><p>State change: {resultEntry ? `${signedDelta(resultEntry.kpi_delta.safe)} safe · ${signedDelta(resultEntry.kpi_delta.waiting)} waiting · ${signedDelta(resultEntry.kpi_delta.in_transit)} on the road` : safeDelta == null ? '— (state unavailable)' : `${safeDelta >= 0 ? '+' : ''}${safeDelta} safe`}</p>{result.certificates.map(cert => <p key={cert.cert_id}><a href={`/decisions?session=${session}&cert=${cert.cert_id}`}>{cert.cert_id}</a> · {cert.kind}</p>)}{result.rechecks.filter(row => row.action === 'MIGRATE' && row.cert_id).map(row => <p key={row.cert_id}>Re-routed automatically as {row.cert_id} (operator notified)</p>)}<button type="button" onClick={onNext} disabled={busy}>Step on</button><a href={`/decisions?session=${session}`}>View in Decisions &amp; Certificates</a></section> : <>
      <div className={styles.columns}><section><h3>Why</h3><ol>{pending.why.map(item => <li key={item}>{item}</li>)}</ol><p>{pending.note}</p></section><section><h3>Safety bound</h3><p>Lower bound {pending.recommendation.lower?.toFixed(3) ?? '—'} · threshold {pending.threshold?.toFixed(3) ?? '—'}</p><progress value={pending.recommendation.lower ?? 0} max={1} aria-label="Lower bound" /><p>{pending.futures_used ?? '—'} futures · {pending.looks ?? '—'} looks</p><h3>Evidence reference</h3><p>Operator-selected audit reference: NDMA Flood Guidelines (2008), page 64, chunk ndma-flood-guidelines-2008-p64-c0. The certificate comes from the simulated forecast, not this text.</p></section><section><h3>Alternatives</h3><ul aria-label="Alternatives">{pending.alternatives.slice(0, 3).map(item => <li key={item.action_key}><b>{subjectSentence(subjectOf(item))}</b> · {item.verdict} · lower {item.lower?.toFixed(3) ?? '—'}<p>{item.comparison}</p>{!item.certified && <p>Not certified — the gate will not dispatch this</p>}<button type="button" aria-label={`Choose ${item.label}`} disabled={busy || (!onClose && !item.certified)} onClick={() => { setChoice('OVERRIDE'); setSelected(item.action_key); onPreview?.(item.action_key); }}>Choose</button>{!item.certified && <button type="button" disabled={busy} onClick={() => onSubmit('OVERRIDE', item.action_key, 'Demo refusal probe: route is not certified')}>Test gate refusal (demo)</button>}</li>)}</ul></section></div>
      {choice !== 'ACCEPT' && <form id="decision-reason" className={styles.reason} onSubmit={event => { event.preventDefault(); if (code) onSubmit(choice, selected, `${code}: ${reason}`); }}><h3>{choice === 'OVERRIDE' ? 'Override' : 'Decline'} details</h3>{choice === 'OVERRIDE' && <label>Alternative <select value={selected} onChange={event => { setSelected(event.target.value); onPreview?.(event.target.value); }}>{pending.alternatives.map(item => <option key={item.action_key} value={item.action_key}>{subjectSentence(subjectOf(item))} · {item.verdict}{item.certified ? '' : ' · the gate will refuse this'}</option>)}<option value="WAIT">HOLD</option></select></label>}<fieldset><legend>Reason code</legend>{CODES.map(item => <label key={item}><input type="radio" name="reason-code" checked={code === item} onChange={() => setCode(item)} />{item}</label>)}</fieldset><label>REASON <input required value={reason} onChange={event => setReason(event.target.value)} /></label><button type="submit" disabled={busy || !code || !reason.trim()}>{choice === 'OVERRIDE' ? 'Confirm override' : 'Confirm reject'}</button></form>}
      <footer className={styles.actions}><button type="button" className={styles.accept} aria-label="Accept" disabled={busy} onClick={() => onSubmit('ACCEPT', '', '')}><b>Accept</b><small>Send this certified suggestion</small></button><button type="button" className={styles.override} aria-label="Override" disabled={busy} onClick={() => setChoice('OVERRIDE')}><b>Override</b><small>Choose another option; reason required</small></button><button type="button" className={styles.decline} aria-label="Decline" disabled={busy} onClick={() => setChoice('REJECT')}><b>Decline</b><small>Send nobody; reason required</small></button></footer>
    </>}
  </div></div>;
}
