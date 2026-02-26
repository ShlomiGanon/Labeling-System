# models.py
# ---------
# This file defines the core data structures, enums, and UI schemas used throughout 
# the Labeling System. It uses a configuration-driven approach where the UI 
# structure for each workflow is defined here and rendered dynamically by the frontend.

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict

# ---------------------------------------------------------------------------
# Enums for Type Safety
# ---------------------------------------------------------------------------

# Supported labeling workflow types.
class WorkflowType(Enum):
    IMAGE_TEXT_RELATIONSHIP = "A"
    ENTITY_SENTIMENT = "B"
    GOLDEN_CAPTION = "C"
    CUSTOM = "CUSTOM"

# Categories for named entities identified in text.
class EntityType(Enum):
    PERSON = "Person"
    ORG = "Org"
    PLACE = "Place"

# Sentiment categories assigned to entities.
class Sentiment(Enum):
    GOOD = "Good"
    BAD = "Bad"
    TRUST = "Trust"
    FEAR = "Fear"
    ANGER = "Anger"

# Categorization of how image and text relate to each other.
class ImageTextRelationship(Enum):
    INDEPENDENT = "Independent"
    CONTEXT_DEPENDENT = "Context-Dependent"
    NOISE = "Noise"

# ---------------------------------------------------------------------------
# UI Schema Definitions for Modular Interface
# ---------------------------------------------------------------------------

# Types of UI components the frontend can render.
class UIComponent(Enum):
    INPUT_TEXT = "input_text"
    TEXTAREA = "textarea"
    BUTTON_GROUP = "button_group"
    SELECT = "select"

# Defines a single input field in a labeling task.
@dataclass
class FieldSchema:
    id: str
    label: str
    component: UIComponent
    placeholder: str = ""
    options: list[str] = field(default_factory=list)

    # Serializes the field schema configuration into a standard dictionary.
    # This format is used by the frontend to dynamically render UI components.
    # Returns a dictionary containing field ID, label, component type, placeholder, and options.
    def to_dict(self) -> dict:
        # Returns a dictionary representation of the field.
        return {
            "id": self.id,
            "label": self.label,
            "component": self.component.value,
            "placeholder": self.placeholder,
            "options": self.options
        }

# Defines a step in a multi-step workflow (like Workflow B).
@dataclass
class StepSchema:
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

# The full UI definition for a specific workflow type.
@dataclass
class WorkflowSchema:
    workflow_type: WorkflowType
    steps: list[StepSchema]

    # Serializes the entire workflow schema, across all steps, into a dictionary.
    # This represents the complete UI blueprint for a labeling task.
    # Returns a dictionary containing the workflow type and its corresponding steps.
    def to_dict(self) -> dict:
        # Iterates over each step schema object and converts it to a dictionary representation.
        # Returns a list of dictionaries.
        return {
            "workflow_type": self.workflow_type.value,
            "steps": [s.to_dict() for s in self.steps]
        }

# ---------------------------------------------------------------------------
# Core Data Models for Labels
# ---------------------------------------------------------------------------

# Minimal representation of a source row to keep backend logic lightweight.
@dataclass
class SourceRow:
    row_id: str
    image_path: str = ""
    text_content: str = ""
    source_csv: str = ""  # Path of the CSV file this row originated from

    # Checks if the row includes a valid image path.
    # Returns True if image_path is not empty.
    def has_image(self) -> bool:
        # Returns a boolean.
        return bool(self.image_path and self.image_path.strip())

    # Checks if the row includes valid text content.
    # Returns True if text_content is not empty.
    def has_text(self) -> bool:
        # Returns a boolean.
        return bool(self.text_content and self.text_content.strip())

# Represents the results from a Workflow A task.
@dataclass
class ImageTextLabel:
    row_id: str
    labeler_name: str
    relationship: ImageTextRelationship

    # Finalizes the label data into a flat dictionary format for CSV export.
    # Returns a dictionary with metadata and label results.
    def to_dict(self) -> dict:
        # Merges metadata and the relationship status into a single record.
        # Returns a dictionary.
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.IMAGE_TEXT_RELATIONSHIP.value,
            "relationship": self.relationship.value,
        }

# Represents the results from a Workflow B task.
@dataclass
class EntitySentimentLabel:
    row_id: str
    labeler_name: str
    entity_name: Optional[str] = None
    entity_type: Optional[EntityType] = None
    topic: Optional[str] = None
    sentiment: Optional[Sentiment] = None

    # Verifies that all mandatory fields for this workflow are populated before submission.
    # Raises a ValueError if any field is missing.
    # Returns None.
    def validate_complete(self):
        # Checks for missing entity name.
        if not self.entity_name: raise ValueError("Entity Name is missing")
        # Checks for missing entity type.
        if not self.entity_type: raise ValueError("Entity Type is missing")
        # Checks for missing topic.
        if not self.topic: raise ValueError("Topic is missing")
        # Checks for missing sentiment.
        if not self.sentiment: raise ValueError("Sentiment is missing")

    # Finalizes the label data into a high-utility dictionary for sentiment analysis results.
    # Returns a flat dictionary representation.
    def to_dict(self) -> dict:
        # Ensures all fields are present before attempting serialization.
        # Returns None or raises an error.
        self.validate_complete()
        
        # Packs all entity and sentiment fields into the final record format.
        # Returns a dictionary.
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.ENTITY_SENTIMENT.value,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type.value,
            "topic": self.topic,
            "sentiment": self.sentiment.value,
        }

# Represents the results from a Workflow C task.
@dataclass
class CaptionLabel:
    row_id: str
    labeler_name: str
    caption: str

    # Validates that the caption is not an empty or whitespace-only string.
    # Returns None.
    def __post_init__(self):
        # Trims white space and checks the length.
        if not self.caption or not self.caption.strip():
            # Raises error if validation fails.
            # Returns a ValueError.
            raise ValueError("Caption cannot be empty")

    # Finalizes the label data for text-to-image relationship analysis.
    # Returns a dictionary.
    def to_dict(self) -> dict:
        # Returns the final flattened data record.
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.GOLDEN_CAPTION.value,
            "caption": self.caption,
        }

# Represents a flexible label structure for user-defined custom workflows.
@dataclass
class CustomLabel:
    row_id: str
    labeler_name: str
    fields: Dict[str, any]

    # Flattens the dynamically structured fields into a standard dictionary.
    # Returns a dictionary combining metadata with custom field values.
    def to_dict(self) -> dict:
        # Starts with the standard metadata header.
        # Returns a dictionary.
        base = {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": WorkflowType.CUSTOM.value,
        }
        # Merges all user-defined fields directly into the record.
        # Returns None.
        base.update(self.fields)
        return base

# ---------------------------------------------------------------------------
# Global Registry for UI Workflows
# ---------------------------------------------------------------------------

# Creates and registers the UI blueprint for Workflow A (Simplified Image-Text).
# This configuration is used to build the frontend form.
WORKFLOW_A_SCHEMA = WorkflowSchema(
    workflow_type=WorkflowType.IMAGE_TEXT_RELATIONSHIP,
    steps=[
        StepSchema(
            title="בדיקת קשר תמונה-טקסט",
            fields=[
                FieldSchema(
                    id="relationship",
                    label="מה סוג הקשר בין התמונה לטקסט?",
                    component=UIComponent.BUTTON_GROUP,
                    options=[r.value for r in ImageTextRelationship]
                )
            ]
        )
    ]
)

# Creates and registers the UI blueprint for Workflow B (Multi-step Entity-Sentiment).
# This configuration is used to build the complex multi-step form.
WORKFLOW_B_SCHEMA = WorkflowSchema(
    workflow_type=WorkflowType.ENTITY_SENTIMENT,
    steps=[
        StepSchema(
            title="צעד 1: זיהוי ישות",
            fields=[
                FieldSchema(
                    id="entity_name",
                    label="שם הישות:",
                    component=UIComponent.INPUT_TEXT,
                    placeholder="הכנס שם ישות..."
                ),
                FieldSchema(
                    id="entity_type",
                    label="סוג הישות:",
                    component=UIComponent.SELECT,
                    options=[e.value for e in EntityType]
                )
            ]
        ),
        StepSchema(
            title="צעד 2: נושא",
            fields=[
                FieldSchema(
                    id="topic",
                    label="מה הנושא העיקרי?",
                    component=UIComponent.INPUT_TEXT,
                    placeholder="כתוב את הנושא..."
                )
            ]
        ),
        StepSchema(
            title="צעד 3: סנטימנט",
            fields=[
                FieldSchema(
                    id="sentiment",
                    label="מה הסנטימנט?",
                    component=UIComponent.BUTTON_GROUP,
                    options=[s.value for s in Sentiment]
                )
            ]
        )
    ]
)

# Creates and registers the UI blueprint for Workflow C (Free-text Captioning).
# This configuration is used to build the descriptive input form.
WORKFLOW_C_SCHEMA = WorkflowSchema(
    workflow_type=WorkflowType.GOLDEN_CAPTION,
    steps=[
        StepSchema(
            title="תיאור תמונה (Golden Caption)",
            fields=[
                FieldSchema(
                    id="caption",
                    label="תאר את התמונה בצורה מפורטת:",
                    component=UIComponent.TEXTAREA,
                    placeholder="הכנס תיאור כאן..."
                )
            ]
        )
    ]
)

# Maps workflow types to their respective UI blueprints for easy lookup.
# Returns a dictionary mapping WorkflowType enums to WorkflowSchema objects.
WORKFLOW_SCHEMAS: Dict[WorkflowType, WorkflowSchema] = {
    WorkflowType.IMAGE_TEXT_RELATIONSHIP: WORKFLOW_A_SCHEMA,
    WorkflowType.ENTITY_SENTIMENT: WORKFLOW_B_SCHEMA,
    WorkflowType.GOLDEN_CAPTION: WORKFLOW_C_SCHEMA,
}
