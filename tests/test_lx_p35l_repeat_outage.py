"""Lane X check: a second outage in one console session reconciles only its own offline dispatches."""

from src.certify.rollout import Outcome, RolloutResult
from src.escrow.outage import OutageEngine
from src.geospatial import load_road_graph


class _Futures:
    def __init__(self, forecast, graph, world, root, horizon_steps, edge_ids=None, **kwargs):
        self.root = root
        self.A_MAX = len(forecast.zone_severity) * len(forecast.shelter_severity) + 1

    def future(self, k):
        return k


def _ok(c, k, ledger, world, params, graph, extra_terms=()):
    return RolloutResult(True, Outcome.OK, 3, float(c.people), True, True, True, None)


def test_repeated_outages_never_reuse_ids_or_re_execute():
    engine = OutageEngine(1_080_001, "v4-medium-dt2-v1", "escrow", futures_factory=_Futures, rollout=_ok,
                          graph=load_road_graph())
    engine.online_step()
    engine.cut()
    engine.offline_step()
    engine.restore()
    first = [row["cert_id"] for row in engine.executed]
    engine.online_step()
    engine.cut()
    engine.offline_step()
    engine.restore()
    second = [row["cert_id"] for row in engine.executed]
    assert first and second and not set(first) & set(second)
    ids = [cert["cert_id"] for cert in engine.base.certificates()]
    ids += [item["certificate"]["cert_id"] for item in engine.certificates]
    assert len(ids) == len(set(ids))
