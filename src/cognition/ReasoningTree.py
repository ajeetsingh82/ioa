from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from enum import Enum
from typing import Optional, List, Dict


# ---------------------------------------------------------
# AggregationType
# ---------------------------------------------------------

class AggregationType(str, Enum):
    """
    Defines how a GROUP of sibling hypotheses contributes
    to the parent node's confidence.
    """
    AND = "AND"        # All children must collapse (min confidence)
    OR = "OR"          # Any child can collapse (max confidence)
    ATOMIC = "ATOMIC"  # Single-child group (no sibling interaction)


# ---------------------------------------------------------
# Hypothesis Lifecycle
# ---------------------------------------------------------

class HypothesisStatus(str, Enum):
    """
    The lifecycle status of a hypothesis node.
    """
    OPEN = "open"           # Created but not evaluated
    EVALUATED = "evaluated" # Confidence calculated
    EXPANDED = "expanded"   # Children generated
    COLLAPSED = "collapsed" # Resolved and committed to belief system
    PRUNED = "pruned"       # Discarded branch


# ---------------------------------------------------------
# ActionType
# ---------------------------------------------------------

class ActionType(str, Enum):
    """
    What action is required to evaluate this hypothesis.
    """
    REASON = "initiate_reasoning"
    ASK_USER = "ask_user"
    FETCH_RAG = "fetch_rag"
    COLLAPSE = "update_belief_system"
    COMPLETE = "reply_to_user"


# ---------------------------------------------------------
# ChildGroup
# ---------------------------------------------------------

class ChildGroup(BaseModel):
    """
    Represents a logical grouping of sibling hypotheses.

    Example:
        Parent expands into:
            A                -> ATOMIC group
            B OR C           -> OR group
            D AND E          -> AND group

    Parent confidence is computed as:
        max(
            score(A),
            max(score(B), score(C)),
            min(score(D), score(E))
        )
    """
    id: UUID = Field(default_factory=uuid4)
    aggregation_type: AggregationType
    child_ids: List[UUID] = Field(default_factory=list)


# ---------------------------------------------------------
# HypothesisNode
# ---------------------------------------------------------

class HypothesisNode(BaseModel):
    """
    A single node in the reasoning graph.

    Important:
    - child_groups define logical structure of expansion.
    - Node itself does NOT define how its children aggregate.
    - Aggregation is per ChildGroup (sibling logic).
    """

    id: UUID = Field(default_factory=uuid4)
    hypothesis: str

    parent_id: Optional[UUID] = None

    # Logical expansion groups
    child_groups: List[ChildGroup] = Field(default_factory=list)

    status: HypothesisStatus = HypothesisStatus.OPEN
    action_type: ActionType = ActionType.REASON

    # Confidence after evaluation
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Link to collapsed belief (if committed)
    belief_id: Optional[UUID] = None

    # Evidence used in evaluation
    evidence_ids: List[UUID] = Field(default_factory=list)


# ---------------------------------------------------------
# ReasoningTree
# ---------------------------------------------------------

class ReasoningTree:
    """
    A logical reasoning structure using grouped AND/OR semantics.

    Supports:
        - Early collapse
        - Mixed logical expansion
        - Confidence propagation
    """

    def __init__(self, root_node: HypothesisNode):
        self._nodes: Dict[UUID, HypothesisNode] = {root_node.id: root_node}
        self.root_id: UUID = root_node.id

    @classmethod
    def create(cls, hypothesis: str) -> "ReasoningTree":
        """
        Creates a new reasoning tree with a single root node.
        """
        root_node = HypothesisNode(
            hypothesis=hypothesis,
            status=HypothesisStatus.OPEN
        )
        return cls(root_node)

    # -----------------------------------------------------
    # Node Management
    # -----------------------------------------------------

    def add_node(
            self,
            hypothesis: str,
            parent_id: UUID,
            group_id: UUID,
            action_type: ActionType = ActionType.REASON
    ) -> Optional[HypothesisNode]:
        """
        Adds a hypothesis under a specific ChildGroup of a parent.

        This ensures logical grouping (AND / OR / ATOMIC).
        """

        parent_node = self.get_node(parent_id)
        if not parent_node:
            return None

        # Find the group
        target_group = next(
            (g for g in parent_node.child_groups if g.id == group_id),
            None
        )
        if not target_group:
            return None

        new_node = HypothesisNode(
            hypothesis=hypothesis,
            parent_id=parent_id,
            action_type=action_type
        )

        self._nodes[new_node.id] = new_node
        target_group.child_ids.append(new_node.id)

        return new_node

    def add_child_group(
            self,
            parent_id: UUID,
            aggregation_type: AggregationType
    ) -> Optional[ChildGroup]:
        """
        Creates a new logical group under a parent node.

        Example:
            group1 = ATOMIC (A)
            group2 = OR (B, C)
            group3 = AND (D, E)
        """

        parent_node = self.get_node(parent_id)
        if not parent_node:
            return None

        new_group = ChildGroup(
            aggregation_type=aggregation_type
        )

        parent_node.child_groups.append(new_group)
        return new_group

    # -----------------------------------------------------
    # Retrieval Helpers
    # -----------------------------------------------------

    def get_node(self, node_id: UUID) -> Optional[HypothesisNode]:
        return self._nodes.get(node_id)

    def get_parent(self, node_id: UUID) -> Optional[HypothesisNode]:
        node = self.get_node(node_id)
        if not node or not node.parent_id:
            return None
        return self._nodes.get(node.parent_id)

    def get_group_children(self, group: ChildGroup) -> List[HypothesisNode]:
        return [
            self._nodes[cid]
            for cid in group.child_ids
            if cid in self._nodes
        ]
