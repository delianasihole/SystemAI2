from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

@dataclass
class ClassificationResult:
    category: str
    confidence: float
    method: str  # "deterministic" or "deterministic_fallback"

@dataclass
class ExtractionField:
    value: Optional[str]
    confidence: float
    source: Optional[str]

@dataclass
class ExtractionResult:
    contact_name: ExtractionField
    email: ExtractionField
    phone: ExtractionField
    company: ExtractionField
    location: ExtractionField
    service: ExtractionField
    intent: ExtractionField
    evidence: List[str] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CRMMatch:
    record_id: Optional[str]
    confidence: float
    status: str  # "strong_match", "possible_match", "no_match"
    duplicate_records: List[str] = field(default_factory=list)

@dataclass
class ActionRecommendation:
    recommended_action: str
    response_required: bool = True

@dataclass
class ResponseDraft:
    required: bool
    draft: Optional[str]
    confidence: float
    grounded_sources: List[str] = field(default_factory=list)

@dataclass
class ApprovalStatus:
    required: bool
    status: str  # "pending", "approved", "rejected", "not_applicable"

@dataclass
class ProcessingResult:
    id: str
    classification: ClassificationResult
    extraction: ExtractionResult
    crm_match: CRMMatch
    recommended_action: str
    owner: Optional[str]
    response: ResponseDraft
    approval: ApprovalStatus
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
