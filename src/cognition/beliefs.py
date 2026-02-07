import json
from pydantic import BaseModel, Field, ValidationError
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from typing import Optional, List

class SourceType(str, Enum):
    RAG = "rag"
    INFERRED = "inferred"
    HUMAN = "human"
    HYBRID = "hybrid"

class EvidenceType(str, Enum):
    RAG_CHUNK = "rag_chunk"
    BELIEF_REFERENCE = "belief_reference"
    EXTERNAL_TOOL = "external_tool"
    HUMAN_INPUT = "human_input"

class Belief(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    hypothesis: str
    result: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[UUID]
    source_type: SourceType
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: EvidenceType
    content: str
    confidence: float = Field(..., ge=0.5, le=1.0)

class BeliefSystem:
    def __init__(self):
        self._beliefs_by_id: dict[UUID, Belief] = {}
        self._evidence_by_id: dict[UUID, Evidence] = {}
        self._beliefs_by_hypothesis: dict[str, List[Belief]] = {}

    def add_belief(self, belief: Belief):
        """
        Adds a belief to the system after verifying its evidence links.
        Raises ValueError if any evidence_id is not found.
        """
        for evidence_id in belief.evidence_ids:
            if evidence_id not in self._evidence_by_id:
                raise ValueError(f"Invalid Belief: Evidence with ID '{evidence_id}' not found for belief '{belief.id}'.")
        
        self._beliefs_by_id[belief.id] = belief
        if belief.hypothesis not in self._beliefs_by_hypothesis:
            self._beliefs_by_hypothesis[belief.hypothesis] = []
        self._beliefs_by_hypothesis[belief.hypothesis].append(belief)

    def get_belief_by_id(self, belief_id: UUID) -> Optional[Belief]:
        """Retrieves a belief by its ID."""
        return self._beliefs_by_id.get(belief_id)

    def get_beliefs_by_hypothesis(self, hypothesis: str) -> List[Belief]:
        """Retrieves a list of beliefs for a given hypothesis."""
        return self._beliefs_by_hypothesis.get(hypothesis, [])

    def add_evidence(self, evidence: Evidence):
        """Adds evidence to the system."""
        self._evidence_by_id[evidence.id] = evidence

    def get_evidence_by_id(self, evidence_id: UUID) -> Optional[Evidence]:
        """Evidence by its ID."""
        return self._evidence_by_id.get(evidence_id)

    def get_evidence_as_json_by_id(self, evidence_ids: List[UUID]) -> str:
        """
        Retrieves evidence for a given list of IDs and returns them as a JSON string.
        """
        target_evidence = [
            self.get_evidence_by_id(evidence_id) for evidence_id in evidence_ids if self.get_evidence_by_id(evidence_id)
        ]
        evidence_list = [e.model_dump(mode='json') for e in target_evidence]
        return json.dumps(evidence_list, indent=2)

    def get_evidences_as_json(self) -> str:
        """Retrieves all evidence in the system and returns them as a JSON string."""
        evidence_list = [e.model_dump(mode='json') for e in self._evidence_by_id.values()]
        return json.dumps(evidence_list, indent=2)

    def get_evidences_as_text(self) -> str:
        """
        Returns a string representation of all evidence.
        Format: <content> with confidence <confidence>
        """
        evidence_lines = [
            f"{evidence.content} with confidence {evidence.confidence}"
            for evidence in self._evidence_by_id.values()
        ]
        return "\n".join(evidence_lines)

    def get_beliefs_as_json_by_confidence(self, confidence_threshold: float) -> str:
        """
        Retrieves beliefs with confidence above a threshold and returns them as a JSON string.
        """
        confident_beliefs = [
            belief for belief in self._beliefs_by_id.values()
            if belief.confidence >= confidence_threshold
        ]
        beliefs_list = [b.model_dump(mode='json') for b in confident_beliefs]
        return json.dumps(beliefs_list, indent=2)

    def belief_system_as_text_by_confidence(self, confidence_threshold: float) -> str:
        """

        Returns a string representation of beliefs above a confidence threshold.
        Format: IF <hypothesis> THEN <result> WITH confidence <confidence>
        """
        confident_beliefs = [
            f"IF {belief.hypothesis} THEN {belief.result} WITH confidence {belief.confidence}"
            for belief in self._beliefs_by_id.values()
            if belief.confidence >= confidence_threshold
        ]
        return "\n".join(confident_beliefs)

    def get_beliefs_as_json_by_id(self, belief_ids: List[UUID]) -> str:
        """
        Retrieves beliefs for a given list of IDs and returns them as a JSON string.
        """
        target_beliefs = [
            self.get_belief_by_id(belief_id) for belief_id in belief_ids if self.get_belief_by_id(belief_id)
        ]
        beliefs_list = [b.model_dump(mode='json') for b in target_beliefs]
        return json.dumps(beliefs_list, indent=2)

    def get_hypothesis_as_json_by_confidence(self, confidence_threshold: float) -> str:
        """
        Retrieves id, hypothesis, and confidence for beliefs above a threshold.
        """
        confident_hypotheses = [
            {
                "id": str(belief.id),
                "hypothesis": belief.hypothesis,
                "confidence": belief.confidence
            }
            for belief in self._beliefs_by_id.values()
            if belief.confidence >= confidence_threshold
        ]
        return json.dumps(confident_hypotheses, indent=2)

    def try_export(self, file_path: str) -> bool:
        """
        Exports all beliefs and evidence to a JSON file.
        Returns True on success, False on failure.
        """
        try:
            data_to_export = {
                "beliefs": [b.model_dump(mode='json') for b in self._beliefs_by_id.values()],
                "evidence": [e.model_dump(mode='json') for e in self._evidence_by_id.values()]
            }
            with open(file_path, 'w') as f:
                json.dump(data_to_export, f, indent=2)
            return True
        except (IOError, TypeError):
            return False

    def try_import(self, file_path: str) -> bool:
        """
        Imports beliefs and evidence from a JSON file. This is an atomic operation.
        If the import file is valid, it replaces the current data. Otherwise, it does nothing.
        Returns True on success, False on failure.
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # 1. Validate and load all data into temporary structures
            temp_evidence_list = [Evidence.model_validate(e_data) for e_data in data.get("evidence", [])]
            temp_beliefs_list = [Belief.model_validate(b_data) for b_data in data.get("beliefs", [])]

            temp_evidence_ids = {e.id for e in temp_evidence_list}

            # 2. Verify that all belief->evidence links are valid within the imported data
            for belief in temp_beliefs_list:
                for evidence_id in belief.evidence_ids:
                    if evidence_id not in temp_evidence_ids:
                        # This import is invalid, so we abort without changing the belief system's state.
                        return False

            # 3. If all data is valid, clear the current state and add the new data
            self._beliefs_by_id.clear()
            self._evidence_by_id.clear()
            self._beliefs_by_hypothesis.clear()

            for evidence in temp_evidence_list:
                self.add_evidence(evidence)
            for belief in temp_beliefs_list:
                self.add_belief(belief) # This will pass, as we've pre-validated
            
            return True
        except (IOError, json.JSONDecodeError, ValidationError, TypeError):
            # This catches file errors, json errors, or pydantic model validation errors
            return False

# Global instance of the belief system
belief_system = BeliefSystem()
