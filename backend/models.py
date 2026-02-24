"""
models.py
---------
This file defines the basic structures (models) for our data.

We have:
1. SourceRow: Represents one line from the input CSV.
2. Three types of labels (A, B, and C) for different types of work.
"""

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Input Data Row
# ---------------------------------------------------------------------------

@dataclass
class SourceRow:
    """
    Represents one row of data that needs a label.
    """
    row_id: str
    image_path: str
    text_content: str

    def has_image(self) -> bool:
        """Does this row have an image?"""
        return bool(self.image_path.strip())

    def has_text(self) -> bool:
        """Does this row have text?"""
        return bool(self.text_content.strip())


# ---------------------------------------------------------------------------
# Workflow A: Image-Text Relationship
# ---------------------------------------------------------------------------

VALID_IMAGE_TEXT_RELATIONSHIPS = {"Independent", "Context-Dependent", "Noise"}

@dataclass
class ImageTextLabel:
    """
    A label for Workflow A.
    The user decides if the image and text are related.
    """
    row_id: str
    labeler_name: str
    relationship: str

    def __post_init__(self):
        """Make sure the data is valid as soon as the object is created."""
        if not self.row_id.strip(): raise ValueError("Must have a row_id")
        if self.relationship not in VALID_IMAGE_TEXT_RELATIONSHIPS:
            raise ValueError(f"Invalid relationship choice: {self.relationship}")

    def to_dict(self) -> dict:
        """Turn this object into a simple dictionary for saving to CSV."""
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": "A_image_text",
            "relationship": self.relationship,
        }


# ---------------------------------------------------------------------------
# Workflow B: Entity & Sentiment
# ---------------------------------------------------------------------------

VALID_ENTITY_TYPES = {"Person", "Org", "Place"}
VALID_SENTIMENTS = {"Good", "Bad", "Trust", "Fear", "Anger"}

@dataclass
class EntitySentimentLabel:
    """
    A label for Workflow B.
    This takes 3 steps: Entity name, Topic, and Sentiment.
    """
    row_id: str
    labeler_name: str
    entity_name: str = ""
    entity_type: str = ""
    topic: str = ""
    sentiment: str = ""

    _is_complete: bool = field(default=False, init=False, repr=False)

    def set_entity(self, name: str, etype: str):
        """Step 1: Save the entity info."""
        if etype not in VALID_ENTITY_TYPES: raise ValueError("Invalid type")
        self.entity_name = name
        self.entity_type = etype

    def set_topic(self, topic: str):
        """Step 2: Save the topic."""
        self.topic = topic

    def set_sentiment(self, sentiment: str):
        """Step 3: Save the sentiment and finish."""
        if sentiment not in VALID_SENTIMENTS: raise ValueError("Invalid sentiment")
        self.sentiment = sentiment
        self._is_complete = True

    def validate_complete(self):
        """Check if all 3 steps were done."""
        if not (self.entity_name and self.topic and self.sentiment):
            raise ValueError("Label is not finished yet!")

    def to_dict(self) -> dict:
        self.validate_complete()
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": "B_entity_sentiment",
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "topic": self.topic,
            "sentiment": self.sentiment,
        }


# ---------------------------------------------------------------------------
# Workflow C: Golden Caption
# ---------------------------------------------------------------------------

@dataclass
class CaptionLabel:
    """
    A label for Workflow C.
    The user writes a description (caption) for the image.
    """
    row_id: str
    labeler_name: str
    caption: str

    def __post_init__(self):
        if not self.caption.strip(): raise ValueError("Caption cannot be empty")

    def to_dict(self) -> dict:
        return {
            "row_id": self.row_id,
            "labeler_name": self.labeler_name,
            "workflow": "C_caption",
            "caption": self.caption,
        }
