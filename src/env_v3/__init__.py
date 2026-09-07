"""Fixed-dimensional Gymnasium API for Sentinel-Agent V3 Phase 7."""

from .action_space import (
    DecodedAction,
    EnvironmentConfigurationError,
    FixedActionMap,
    decode_action,
    encode_dispatch,
)
from .config import (
    ACTION_COUNT,
    DEFAULT_ENV_CONFIG,
    ENV_CONFIG_ID,
    MAX_SHELTERS,
    MAX_ZONES,
    PLACEHOLDER_REWARD_VERSION,
    WAIT_INDEX,
    EnvV3Config,
    ZeroPlaceholderReward,
)
from .evacuation_env import EvacuationEnvV3
from .observation import (
    GLOBAL_FEATURES,
    OBSERVATION_DIM,
    ROUTE_FEATURES,
    SHELTER_FEATURES,
    ZONE_FEATURES,
    ObservationValueError,
    build_observation,
    observation_dimension,
)
from .scenario_source import (
    CallableScenarioSource,
    FixedScenarioSource,
    ResetContext,
    ScenarioSource,
)

__all__ = [
    "ACTION_COUNT",
    "CallableScenarioSource",
    "DEFAULT_ENV_CONFIG",
    "DecodedAction",
    "ENV_CONFIG_ID",
    "EnvV3Config",
    "EnvironmentConfigurationError",
    "EvacuationEnvV3",
    "FixedActionMap",
    "FixedScenarioSource",
    "GLOBAL_FEATURES",
    "MAX_SHELTERS",
    "MAX_ZONES",
    "OBSERVATION_DIM",
    "ObservationValueError",
    "PLACEHOLDER_REWARD_VERSION",
    "ROUTE_FEATURES",
    "ResetContext",
    "SHELTER_FEATURES",
    "ScenarioSource",
    "WAIT_INDEX",
    "ZONE_FEATURES",
    "ZeroPlaceholderReward",
    "build_observation",
    "decode_action",
    "encode_dispatch",
    "observation_dimension",
]
