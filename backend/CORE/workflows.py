"""
workflows.py
------------
Implements the high-level logic for different labeling tasks.
It manages state for multi-step workflows like Workflow B.
"""

from typing import Dict, Tuple
from models import (
    ImageTextLabel, 
    EntitySentimentLabel, 
    CaptionLabel,
    CustomLabel,
    ImageTextRelationship, 
    EntityType, 
    Sentiment
)
from labeling_engine import LabelingEngine

# Internal cache for labels that are still in progress.
# Used for Workflow B which requires 3 separate user interactions.
# Key: (username, row_id) - uniquely identifies a user's work session on a row.
_pending_entity_labels: Dict[Tuple[str, str], EntitySentimentLabel] = {}

# ===========================================================================
# Workflow A: Image-Text Relationship
# ===========================================================================

def process_image_text_relationship(engine: LabelingEngine, user_name: str, row_id: str, relationship: str) -> bool:
    """
    Workflow A: Processes a simple one-step image-text relationship label.

    Args:
        engine (LabelingEngine): The engine to handle data persistence.
        user_name (str): Name of the labeler.
        row_id (str): ID of the row being labeled.
        relationship (str): The chosen relationship type.

    Returns:
        bool: True if the label was successfully saved.
    """
    label = ImageTextLabel(row_id=row_id, labeler_name=user_name, relationship=relationship)
    
    # Request the engine to persist the completed label.
    return engine.submit_label(user_name, label)


# ===========================================================================
# Workflow B: Entity & Sentiment (Multi-Step Process)
# ===========================================================================

def process_entity_identification(user_name: str, row_id: str, entity_name: str, entity_type: str) -> EntitySentimentLabel:
    """
    Step 1: Initiates a new sentiment label by identifying the primary entity.
    The label is stored in memory and not yet saved to disk.

    Args:
        user_name (str): Name of the labeler.
        row_id (str): ID of the row.
        entity_name (str): Name identified in the text/image.
        entity_type (str): Category of the entity (Person, Org, Place).

    Returns:
        EntitySentimentLabel: The initialized label object.
    """
    label = EntitySentimentLabel(row_id=row_id, labeler_name=user_name)
    label.set_entity(entity_name, entity_type)

    # Store in memory using a composite key of user and row.
    _pending_entity_labels[(user_name, row_id)] = label
    return label

def process_topic_assignment(user_name: str, row_id: str, topic: str) -> EntitySentimentLabel:
    """
    Step 2: Assigns a topic to the label initiated in Step 1.

    Args:
        user_name (str): Name of the labeler.
        row_id (str): ID of the row.
        topic (str): The topic relevance.

    Returns:
        EntitySentimentLabel: The updated label object.

    Raises:
        KeyError: If Step 1 was not performed for this user/row.
    """
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        raise KeyError("Workflow Error: You must identify an entity (Step 1) before assigning a topic.")

    label = _pending_entity_labels[key]
    label.set_topic(topic)
    return label

def process_entity_sentiment(engine: LabelingEngine, user_name: str, row_id: str, sentiment: str) -> bool:
    """
    Step 3: Finalizes the workflow by setting the sentiment and persisting the full label.

    Args:
        engine (LabelingEngine): The engine to handle data persistence.
        user_name (str): Name of the labeler.
        row_id (str): ID of the row.
        sentiment (str): The sentiment choice.

    Returns:
        bool: True if the full multi-step label was saved successfully.

    Raises:
        KeyError: If prior steps were skipped.
    """
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        raise KeyError("Workflow Error: You must complete identification and topic assignment before sentiment.")

    label = _pending_entity_labels[key]
    label.set_sentiment(sentiment)

    # All three steps are complete. Persist the data via the engine.
    success = engine.submit_label(user_name, label)

    # Cleanup: If saved successfully, remove from memory to free space and prevent state leaks.
    if success:
        del _pending_entity_labels[key]
    
    return success


# ===========================================================================
# Workflow C: Golden Caption
# ===========================================================================

def process_caption(engine: LabelingEngine, user_name: str, row_id: str, caption: str) -> bool:
    """
    Workflow C: Processes a simple one-step caption/description label.

    Args:
        engine (LabelingEngine): The engine to handle data persistence.
        user_name (str): Name of the labeler.
        row_id (str): ID of the row.
        caption (str): The user-written description.

    Returns:
        bool: True if the caption was saved successfully.
    """
    label = CaptionLabel(row_id=row_id, labeler_name=user_name, caption=caption)
    return engine.submit_label(user_name, label)


# ===========================================================================
# Custom Workflow: Generic field submission
# ===========================================================================

def process_custom_workflow(engine: LabelingEngine, user_name: str, row_id: str, fields: dict) -> bool:
    """
    Custom Workflow: Saves any arbitrary set of field values to the master CSV.
    Works for any user-defined workflow schema without requiring code changes.

    Args:
        engine (LabelingEngine): The engine to handle data persistence.
        user_name (str): Name of the labeler.
        row_id (str): ID of the row being labeled.
        fields (dict): All field id -> value pairs collected from the frontend form.

    Returns:
        bool: True if the custom label was saved successfully.
    """
    # Strip out the row_id from fields if the frontend accidentally included it
    fields.pop("row_id", None)
    label = CustomLabel(row_id=row_id, labeler_name=user_name, fields=fields)
    return engine.submit_label(user_name, label)


# Internal cache for labels that are still in progress.
# Used for Workflow B which requires 3 separate user interactions.
# Key: (username, row_id) - uniquely identifies a user's work session on a row.
_pending_entity_labels: Dict[Tuple[str, str], EntitySentimentLabel] = {}

# ===========================================================================
# Workflow A: Image-Text Relationship
# ===========================================================================

def process_image_text_relationship(engine: LabelingEngine, user_name: str, row_id: str, relationship: str) -> bool:
    """
    Workflow A: Processes a simple one-step image-text relationship label.

    Args:
        engine (LabelingEngine): The engine to handle data persistence.
        user_name (str): Name of the labeler.
        row_id (str): ID of the row being labeled.
        relationship (str): The chosen relationship type.

    Returns:
        bool: True if the label was successfully saved.
    """
    label = ImageTextLabel(row_id=row_id, labeler_name=user_name, relationship=relationship)
    
    # Request the engine to persist the completed label.
    return engine.submit_label(user_name, label)


# ===========================================================================
# Workflow B: Entity & Sentiment (Multi-Step Process)
# ===========================================================================

def process_entity_identification(user_name: str, row_id: str, entity_name: str, entity_type: str) -> EntitySentimentLabel:
    """
    Step 1: Initiates a new sentiment label by identifying the primary entity.
    The label is stored in memory and not yet saved to disk.

    Args:
        user_name (str): Name of the labeler.
        row_id (str): ID of the row.
        entity_name (str): Name identified in the text/image.
        entity_type (str): Category of the entity (Person, Org, Place).

    Returns:
        EntitySentimentLabel: The initialized label object.
    """
    label = EntitySentimentLabel(row_id=row_id, labeler_name=user_name)
    label.set_entity(entity_name, entity_type)

    # Store in memory using a composite key of user and row.
    _pending_entity_labels[(user_name, row_id)] = label
    return label

def process_topic_assignment(user_name: str, row_id: str, topic: str) -> EntitySentimentLabel:
    """
    Step 2: Assigns a topic to the label initiated in Step 1.

    Args:
        user_name (str): Name of the labeler.
        row_id (str): ID of the row.
        topic (str): The topic relevance.

    Returns:
        EntitySentimentLabel: The updated label object.

    Raises:
        KeyError: If Step 1 was not performed for this user/row.
    """
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        raise KeyError("Workflow Error: You must identify an entity (Step 1) before assigning a topic.")

    label = _pending_entity_labels[key]
    label.set_topic(topic)
    return label

def process_entity_sentiment(engine: LabelingEngine, user_name: str, row_id: str, sentiment: str) -> bool:
    """
    Step 3: Finalizes the workflow by setting the sentiment and persisting the full label.

    Args:
        engine (LabelingEngine): The engine to handle data persistence.
        user_name (str): Name of the labeler.
        row_id (str): ID of the row.
        sentiment (str): The sentiment choice.

    Returns:
        bool: True if the full multi-step label was saved successfully.

    Raises:
        KeyError: If prior steps were skipped.
    """
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        raise KeyError("Workflow Error: You must complete identification and topic assignment before sentiment.")

    label = _pending_entity_labels[key]
    label.set_sentiment(sentiment)

    # All three steps are complete. Persist the data via the engine.
    success = engine.submit_label(user_name, label)

    # Cleanup: If saved successfully, remove from memory to free space and prevent state leaks.
    if success:
        del _pending_entity_labels[key]
    
    return success


# ===========================================================================
# Workflow C: Golden Caption
# ===========================================================================

def process_caption(engine: LabelingEngine, user_name: str, row_id: str, caption: str) -> bool:
    """
    Workflow C: Processes a simple one-step caption/description label.

    Args:
        engine (LabelingEngine): The engine to handle data persistence.
        user_name (str): Name of the labeler.
        row_id (str): ID of the row.
        caption (str): The user-written description.

    Returns:
        bool: True if the caption was saved successfully.
    """
    label = CaptionLabel(row_id=row_id, labeler_name=user_name, caption=caption)
    return engine.submit_label(user_name, label)
