"""
==============================================================================
EIMS Canonical Asset Lifecycle State Machine
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 3 Section 6.4
Source-Available All Rights Reserved Policy
==============================================================================
"""

from enum import Enum
from typing import Set, Dict
from backend.core.exceptions import AssetStateViolationException
from backend.core.logger import get_logger

logger = get_logger("eims.domain.state_machine")


class AssetState(str, Enum):
    """
    Authoritative enumeration of permissible infrastructure asset lifecycle states
    defined in Core Law 3 Section 6.4 stateDiagram-v2 matrix.
    """
    DISCOVERED = "Discovered"
    PENDING_AUDIT = "PendingAudit"
    COMPLIANT = "Compliant"
    NON_COMPLIANT = "NonCompliant"
    QUARANTINED = "Quarantined"
    DECOMMISSIONED = "Decommissioned"


class AssetLifecycleStateMachine:
    """
    Authoritative computational evaluation engine enforcing canonical lifecycle transition
    boundaries. Prohibits illegal state jumps to protect platform security and compliance audit trails.
    """

    # Directional Graph Adjacency Matrix mapping current state -> set of permitted target states
    _ALLOWED_TRANSITIONS: Dict[AssetState, Set[AssetState]] = {
        AssetState.DISCOVERED: {
            AssetState.PENDING_AUDIT,
        },
        AssetState.PENDING_AUDIT: {
            AssetState.COMPLIANT,
            AssetState.NON_COMPLIANT,
            AssetState.QUARANTINED,
        },
        AssetState.COMPLIANT: {
            AssetState.NON_COMPLIANT,
            AssetState.QUARANTINED,
            AssetState.DECOMMISSIONED,
        },
        AssetState.NON_COMPLIANT: {
            AssetState.COMPLIANT,
            AssetState.QUARANTINED,
            AssetState.DECOMMISSIONED,
        },
        AssetState.QUARANTINED: {
            AssetState.PENDING_AUDIT,
            AssetState.DECOMMISSIONED,
        },
        AssetState.DECOMMISSIONED: set(),  # Terminal read-only historical archival state
    }

    @classmethod
    def validate_transition(cls, current_state: str, target_state: str, asset_id: str) -> None:
        """
        Evaluates proposed state mutation against Core Law 3 graph invariants.
        
        Raises:
            AssetStateViolationException (HTTP 409 Conflict) if transition is unauthorized.
        """
        try:
            curr_enum = AssetState(current_state)
            target_enum = AssetState(target_state)
        except ValueError as e:
            logger.warning(f"Unrecognized state literal encountered during transition evaluation: {e}")
            raise AssetStateViolationException(current_state=current_state, attempted_state=target_state, asset_id=asset_id)

        allowed = cls._ALLOWED_TRANSITIONS.get(curr_enum, set())
        
        if target_enum not in allowed:
            logger.warning(
                f"ILLEGAL STATE TRANSITION BLOCKED | Asset={asset_id} | Current={current_state} -> Attempted={target_state}"
            )
            raise AssetStateViolationException(
                current_state=current_state,
                attempted_state=target_state,
                asset_id=asset_id
            )
            
        logger.info(
            f"State transition authorized by Core Law 3 Matrix | Asset={asset_id} | {current_state} -> {target_state}"
        )

    @classmethod
    def get_permitted_transitions(cls, current_state: str) -> Set[str]:
        """Returns set of legal forward transition target strings for developer diagnostics."""
        try:
            curr_enum = AssetState(current_state)
            return {state.value for state in cls._ALLOWED_TRANSITIONS.get(curr_enum, set())}
        except ValueError:
            return set()
