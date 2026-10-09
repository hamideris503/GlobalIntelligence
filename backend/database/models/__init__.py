"""ORM models for GlobalIntelligence.

همه‌ی مدل‌ها برای `Alembic autogenerate` باید در `backend.database.models` import شوند.
"""
from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.entity import Entity, EntityRelationship
from backend.database.models.event import Event
from backend.database.models.evidence import Evidence
from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.models.job import JobRun
from backend.database.models.macro_assessment import MacroAssessment
from backend.database.models.market import MacroObservation, MarketObservation
from backend.database.models.memory import MemoryRecord
from backend.database.models.narrative import Narrative
from backend.database.models.recommendation import Recommendation
from backend.database.models.scenario import Scenario
from backend.database.models.social_assessment import SocialAssessment
from backend.database.models.source import Source
from backend.database.models.source_dependency import SourceDependency
from backend.database.models.tournament import Tournament
from backend.database.models.world_state import WorldState

__all__ = [
    "Article",
    "Claim",
    "Document",
    "Entity",
    "EntityRelationship",
    "Event",
    "Evidence",
    "Forecast",
    "ForecastOutcome",
    "GeopoliticalAssessment",
    "JobRun",
    "MacroAssessment",
    "MacroObservation",
    "MarketObservation",
    "MemoryRecord",
    "Narrative",
    "Recommendation",
    "Scenario",
    "SocialAssessment",
    "Source",
    "SourceDependency",
    "Tournament",
    "WorldState",
]
