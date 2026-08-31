from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

@dataclass
class ClassificationResult:
    category: str
    confidence: float
    method: str  # "deterministic", "deterministic_fallback", "llm", or "llm_error"

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
    status: str  # "pending", "approved", "rejected", "not_applicable", "pending_manual_review"

@dataclass
class ContactFieldHistory:
    """One value a field held, and which email it came from - kept alongside
    every other value the field has held rather than overwriting them, so a
    correction never silently erases what was said before."""
    field: str  # "phone" or "email"
    value: Optional[str]
    source_email_id: str
    is_correction: bool  # True for the newer, preferred value


@dataclass
class OpportunityCorrection:
    """Two emails recognised as the same opportunity because a later one
    explicitly, verifiably corrects a value from an earlier one - see
    scr/correlator.py for the three-signal rule that produces this."""
    email_ids: List[str]  # [earlier_id, later_id]
    history: List[ContactFieldHistory]
    preferred_phone: Optional[str]
    preferred_email: Optional[str]
    reason: str


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
