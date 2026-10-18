import type { Run, Trace } from './types';
import type { MapGeometry } from '../types';
import { SimulationMap } from '../live/OperationsMap';
import styles from './Sims.module.css';

export default function CompareView({ trace, baseline, geometry, index }: { trace: Trace; baseline?: Run; geometry: MapGeometry; index: number }) {
  return <section aria-label="Side by side system comparison"><h2>Same world and seed · P versus {baseline?.system ?? 'baseline'}</h2><div className={styles.compare}>
    <div><SimulationMap geometry={geometry} step={trace.steps[index]} label="P · recorded step" /><p>Final safe — · stranded — · unsafe — <small>See run explorer for final P totals.</small></p></div>
    <div className={styles.summaryOnly}><h3>{baseline?.system ?? 'No baseline selected'}</h3><p>Per-step map: —</p><p>No per-step trace exists for this system and seed. The map is intentionally unavailable.</p>{baseline && <div className={styles.metrics}><span>Final safe <b>{baseline.people_safely_arrived}</b></span><span>Final stranded <b>{baseline.stranded_people}</b></span><span>Final unsafe <b>{baseline.unsafe_people}</b></span></div>}<small>{baseline?.source_path ?? 'Run summary unavailable'}</small></div>
  </div></section>;
}
