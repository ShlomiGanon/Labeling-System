"""
models.py
---------
This file defines the core data structures and enums used throughout the Labeling System.
It uses Python's dataclasses for data storage and Enum for categorical values.
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
