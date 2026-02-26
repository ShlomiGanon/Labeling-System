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

    # Serializes the field schema configuration into a standard dictionary.
    # This format is used by the frontend to dynamically render UI components.
    # Returns a dictionary containing field ID, label, component type, placeholder, and options.
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

    # Serializes the step schema, including all nested field definitions, into a dictionary.
    # This allows the frontend to group related input fields under a single step title.
    # Returns a dictionary with the step title and a list of serialized fields.
    def to_dict(self) -> dict:
        # Iterates over each field schema object and converts it to a dictionary representation.
        # Returns a list of dictionaries.
        return {
            "title": self.title,
            "fields": [f.to_dict() for f in self.fields]
        }

@dataclass
class WorkflowSchema:
    """The full UI definition for a specific workflow type."""
    workflow_type: WorkflowType
    steps: list[StepSchema]

    # Serializes the entire workflow schema, across all steps, into a dictionary.
    # This represents the complete UI blueprint for a labeling task.
    # Returns a dictionary containing the workflow type and a list of serialized steps.
    def to_dict(self) -> dict:
        # Iterates through each step schema and converts it to a dictionary.
        # Returns a list of dictionaries.
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
    # Represents a single unit of work (a row from a CSV).
    row_id: str
    image_path: str
    text_content: str

    # Determines if the current source row contains a valid reference to an image.
    # It checks if the image path is provided and contains non-whitespace characters.
    # Returns True if an image path is present, False otherwise.
    def has_image(self) -> bool:
        # Converts the image path to a string and removes leading/trailing whitespace.
        # Returns a cleaned string.
        return bool(self.image_path and str(self.image_path).strip())

    # Determines if the current source row contains text content available for labeling.
    # It verifies that the text content is not None and not empty when whitespace is removed.
    # Returns True if text content is present, False otherwise.
    def has_text(self) -> bool:
        # Converts the text content to a string and removes leading/trailing whitespace.
        # Returns a cleaned string.
        return bool(self.text_content and str(self.text_content).strip())


@dataclass
class ImageTextLabel:
    # Result of Workflow A: Categorizing the Image-Text relationship.
    row_id: str
    labeler_name: str
    relationship: ImageTextRelationship

    # Validates the integrity of the Image-Text label data immediately after initialization.
    # It ensures that a unique row identifier is provided for the labeling result.
    # It does not return anything, but raises a ValueError on failure.
    def __post_init__(self):
        # Removes whitespace from the row ID to check for empty input.
        # Returns a cleaned string.
        if not self.row_id.strip(): 
            raise ValueError("Row ID cannot be empty.")

    # Serializes the Image-Text relationship label into a flat dictionary for storage.
    # It explicitly identifies the workflow type and extracts the value from the relationship enum.
    # Returns a dictionary representing the finalized label data.
    def to_dict(self) -> dict:
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.IMAGE_TEXT_RELATIONSHIP.value,
            "relationship": self.relationship.value,
        }


@dataclass
class EntitySentimentLabel:
    # Result of Workflow B: A multi-step identification and sentiment analysis.
    row_id: str
    labeler_name: str
    entity_name: str = ""
    entity_type: Optional[EntityType] = None
    topic: str = ""
    sentiment: Optional[Sentiment] = None

    # Internal state flag, hidden from init/repr
    _is_complete: bool = field(default=False, init=False, repr=False)

    # Records the first step of the workflow by identifying the entity name and its category.
    # This prepares the label object for subsequent topic and sentiment assignment.
    # It does not return anything.
    def set_entity(self, name: str, etype: EntityType):
        self.entity_name = name
        self.entity_type = etype

    # Records the second step of the workflow by assigning a specific topic or context to the entity.
    # This helps in classifying the thematic area of the text content.
    # It does not return anything.
    def set_topic(self, topic: str):
        self.topic = topic

    # Completes the final step of the workflow by assigning a sentiment category to the entity.
    # This marks the entire labeling unit as complete and ready for submission.
    # It does not return anything.
    def set_sentiment(self, sentiment: Sentiment):
        self.sentiment = sentiment
        self._is_complete = True

    # Verifies that all mandatory labeling steps (Entity, Topic, and Sentiment) have been completed.
    # This is used as a safety check before data persistence.
    # It does not return anything, but raises a ValueError if steps are missing.
    def validate_complete(self):
        if not (self.entity_name and self.topic and self.sentiment):
            raise ValueError("Incomplete workflow: Entity, Topic, and Sentiment are all required.")

    # Serializes the multi-step Entity-Sentiment label data into a dictionary for CSV storage.
    # It first performs a completeness check to ensure all required fields are populated.
    # Returns a dictionary containing row metadata and all finalized labeling fields.
    def to_dict(self) -> dict:
        # Ensures that the workflow has been completed through all required steps.
        # Returns None or raises an exception.
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
    # Result of Workflow C: User-provided descriptive caption for an image.
    row_id: str
    labeler_name: str
    caption: str

    # Validates that a descriptive caption has been provided by the user.
    # It prevents the submission of empty or whitespace-only labels.
    # It does not return anything, but raises a ValueError on failure.
    def __post_init__(self):
        # Removes whitespace from the caption text to verify content existence.
        # Returns a cleaned string.
        if not self.caption.strip(): 
            raise ValueError("Caption cannot be empty.")

    # Serializes the caption label into a dictionary format compatible with CSV output.
    # It maps the internal attributes to standard export keys.
    # Returns a dictionary representing the finalized image description.
    def to_dict(self) -> dict:
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.GOLDEN_CAPTION.value,
            "caption": self.caption,
        }


@dataclass
class CustomLabel:
    # Result of a user-defined Custom Workflow.
    # Stores any arbitrary set of field values as submitted by the labeler.
    # This makes the system fully modular – no code changes needed to add new workflows.
    row_id: str
    labeler_name: str
    fields: dict  # e.g. {"sentiment": "Good", "entity": "ישות 1"}

    # Validates that the custom labeling result contains both a row ID and at least one data field.
    # It ensures the modular workflow data is substantial enough for storage.
    # It does not return anything, but raises a ValueError on failure.
    def __post_init__(self):
        # Removes whitespace from the row ID to check for missing input.
        # Returns a cleaned string.
        if not self.row_id.strip():
            raise ValueError("Row ID cannot be empty.")
        if not self.fields:
            raise ValueError("Custom label must have at least one field value.")

    # Merges metadata with user-defined custom fields into a single flat dictionary.
    # This flexible structure supports dynamic forms without backend schema changes.
    # Returns a flat dictionary containing row_id, labeler_name, workflow, and all custom data.
    def to_dict(self) -> dict:
        base = {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.CUSTOM.value,
        }
        # Merges all dynamically defined field values into the base metadata dictionary.
        # Returns None (modifies the base dictionary in-place).
        base.update(self.fields)
        return base
