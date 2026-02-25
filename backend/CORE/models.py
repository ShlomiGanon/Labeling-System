"""
models.py
---------
This file defines the core data structures, enums, and UI schemas used throughout 
the Labeling System. It uses a configuration-driven approach where the UI 
structure for each workflow is defined here and rendered dynamically by the frontend.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict

# ---------------------------------------------------------------------------
# Enums for Type Safety
# ---------------------------------------------------------------------------

class WorkflowType(Enum):
    """Supported labeling workflow types."""
    IMAGE_TEXT_RELATIONSHIP = "A"
    ENTITY_SENTIMENT = "B"
    GOLDEN_CAPTION = "C"
    CUSTOM = "CUSTOM"

class EntityType(Enum):
    """Categories for named entities identified in text."""
    PERSON = "Person"
    ORG = "Org"
    PLACE = "Place"

class Sentiment(Enum):
    """Sentiment categories assigned to entities."""
    GOOD = "Good"
    BAD = "Bad"
    TRUST = "Trust"
    FEAR = "Fear"
    ANGER = "Anger"

class ImageTextRelationship(Enum):
    """Categorization of how image and text relate to each other."""
    INDEPENDENT = "Independent"
    CONTEXT_DEPENDENT = "Context-Dependent"
    NOISE = "Noise"

# ---------------------------------------------------------------------------
# UI Schema Definitions for Modular Interface
# ---------------------------------------------------------------------------

class UIComponent(Enum):
    """Types of UI components the frontend can render."""
    INPUT_TEXT = "input_text"
    TEXTAREA = "textarea"
    BUTTON_GROUP = "button_group"
    SELECT = "select"

@dataclass
class FieldSchema:
    """Defines a single input field in a labeling task."""
    id: str
    label: str
    component: UIComponent
    placeholder: str = ""
    options: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "component": self.component.value,
            "placeholder": self.placeholder,
            "options": self.options
        }

@dataclass
class StepSchema:
    """Defines a step in a multi-step workflow (like Workflow B)."""
    title: str
    fields: list[FieldSchema]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "fields": [f.to_dict() for f in self.fields]
        }

@dataclass
class WorkflowSchema:
    """The full UI definition for a specific workflow type."""
    workflow_type: WorkflowType
    steps: list[StepSchema]

    def to_dict(self) -> dict:
        return {
            "workflow_type": self.workflow_type.value,
            "steps": [s.to_dict() for s in self.steps]
        }

# ---------------------------------------------------------------------------
# Pre-defined Workflow Schemas
# ---------------------------------------------------------------------------

WORKFLOW_A_SCHEMA = WorkflowSchema(
    workflow_type=WorkflowType.IMAGE_TEXT_RELATIONSHIP,
    steps=[
        StepSchema(
            title="ניתוח הקשר בין תמונה לטקסט",
            fields=[
                FieldSchema(
                    id="relationship",
                    label="מהו סוג הקשר?",
                    component=UIComponent.BUTTON_GROUP,
                    options=[r.value for r in ImageTextRelationship]
                )
            ]
        )
    ]
)

WORKFLOW_B_SCHEMA = WorkflowSchema(
    workflow_type=WorkflowType.ENTITY_SENTIMENT,
    steps=[
        StepSchema(
            title="שלב 1 – זיהוי ישות מרכזית",
            fields=[
                FieldSchema(
                    id="entity_name",
                    label="שם הישות",
                    component=UIComponent.SELECT,
                    options=["ישות 1", "ישות 2", "ישות 3"]
                ),
                FieldSchema(
                    id="entity_type",
                    label="סוג הישות",
                    component=UIComponent.BUTTON_GROUP,
                    options=[t.value for t in EntityType]
                )
            ]
        ),
        StepSchema(
            title="שלב 2 – קביעת נושא הטקסט",
            fields=[
                FieldSchema(
                    id="topic",
                    label="הנושא העיקרי",
                    component=UIComponent.INPUT_TEXT,
                    placeholder="למשל: שינויים בריבית במשק"
                )
            ]
        ),
        StepSchema(
            title="שלב 3 – הערכת סנטימנט",
            fields=[
                FieldSchema(
                    id="sentiment",
                    label="סנטימנט",
                    component=UIComponent.BUTTON_GROUP,
                    options=[s.value for s in Sentiment]
                )
            ]
        )
    ]
)

WORKFLOW_C_SCHEMA = WorkflowSchema(
    workflow_type=WorkflowType.GOLDEN_CAPTION,
    steps=[
        StepSchema(
            title="כתיבת כיתוב תיאורי (Caption)",
            fields=[
                FieldSchema(
                    id="caption",
                    label="הכיתוב המוצע",
                    component=UIComponent.TEXTAREA,
                    placeholder="תאר את הפרטים המופיעים בתמונה..."
                )
            ]
        )
    ]
)

WORKFLOW_SCHEMAS = {
    WorkflowType.IMAGE_TEXT_RELATIONSHIP: WORKFLOW_A_SCHEMA,
    WorkflowType.ENTITY_SENTIMENT: WORKFLOW_B_SCHEMA,
    WorkflowType.GOLDEN_CAPTION: WORKFLOW_C_SCHEMA
}

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SourceRow:
    """
    Represents a single unit of work (a row from a CSV).
    
    Attributes:
        row_id (str): A unique identifier for the row.
        image_path (str): Path or URL to the associated image.
        text_content (str): Textual content to be labeled.
    """
    row_id: str
    image_path: str
    text_content: str

    def has_image(self) -> bool:
        """
        Checks if this row actually contains an image reference.
        
        Returns:
            bool: True if image_path is not just whitespace.
        """
        return bool(self.image_path.strip())

    def has_text(self) -> bool:
        """
        Checks if this row contains text to be analyzed.
        
        Returns:
            bool: True if text_content is not just whitespace.
        """
        return bool(self.text_content.strip())


@dataclass
class ImageTextLabel:
    """
    Result of Workflow A: Categorizing the Image-Text relationship.
    """
    row_id: str
    labeler_name: str
    relationship: ImageTextRelationship

    def __post_init__(self):
        """
        Ensures the data is valid upon creation.
        """
        if not self.row_id.strip(): 
            raise ValueError("Row ID cannot be empty.")

    def to_dict(self) -> dict:
        """
        Converts the label object to a flat dictionary for CSV serialization.
        
        Returns:
            dict: The dictionary representation of the label.
        """
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.IMAGE_TEXT_RELATIONSHIP.value,
            "relationship": self.relationship.value,
        }


@dataclass
class EntitySentimentLabel:
    """
    Result of Workflow B: A multi-step identification and sentiment analysis.
    """
    row_id: str
    labeler_name: str
    entity_name: str = ""
    entity_type: Optional[EntityType] = None
    topic: str = ""
    sentiment: Optional[Sentiment] = None

    # Internal state flag, hidden from init/repr
    _is_complete: bool = field(default=False, init=False, repr=False)

    def set_entity(self, name: str, etype: EntityType):
        """
        Records the first step: identifying an entity.
        
        Args:
            name (str): The name of the entity.
            etype (EntityType): The category of the entity.
        """
        self.entity_name = name
        self.entity_type = etype

    def set_topic(self, topic: str):
        """
        Records the second step: assigning a topic/context.
        
        Args:
            topic (str): The topic relevance.
        """
        self.topic = topic

    def set_sentiment(self, sentiment: Sentiment):
        """
        Final step: setting the sentiment and marking as complete.
        
        Args:
            sentiment (Sentiment): The emotional category.
        """
        self.sentiment = sentiment
        self._is_complete = True

    def validate_complete(self):
        """
        Verifies that all mandatory steps have been performed.
        
        Raises:
            ValueError: If the workflow is incomplete.
        """
        if not (self.entity_name and self.topic and self.sentiment):
            raise ValueError("Incomplete workflow: Entity, Topic, and Sentiment are all required.")

    def to_dict(self) -> dict:
        """
        Prepares the data for CSV storage.
        
        Returns:
            dict: Serialized label data.
        """
        self.validate_complete()
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.ENTITY_SENTIMENT.value,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type.value,
            "topic": self.topic,
            "sentiment": self.sentiment.value,
        }


@dataclass
class CaptionLabel:
    """
    Result of Workflow C: User-provided descriptive caption for an image.
    """
    row_id: str
    labeler_name: str
    caption: str

    def __post_init__(self):
        """
        Ensures the caption is valid.
        """
        if not self.caption.strip(): 
            raise ValueError("Caption cannot be empty.")

    def to_dict(self) -> dict:
        """
        Returns:
            dict: The dictionary representation for CSV export.
        """
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.GOLDEN_CAPTION.value,
            "caption": self.caption,
        }


@dataclass
class CustomLabel:
    """
    Result of a user-defined Custom Workflow.
    Stores any arbitrary set of field values as submitted by the labeler.
    This makes the system fully modular – no code changes needed to add new workflows.
    """
    row_id: str
    labeler_name: str
    fields: dict  # e.g. {"sentiment": "Good", "entity": "ישות 1"}

    def __post_init__(self):
        if not self.row_id.strip():
            raise ValueError("Row ID cannot be empty.")
        if not self.fields:
            raise ValueError("Custom label must have at least one field value.")

    def to_dict(self) -> dict:
        """
        Flattens the label into a dict for CSV export.
        Merges metadata with all user-defined field values.

        Returns:
            dict: A flat dictionary with row_id, labeler_name, workflow, and all custom fields.
        """
        base = {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.CUSTOM.value,
        }
        # Merge all user-submitted fields directly into the row
        base.update(self.fields)
        return base

