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

# Processes a one-step image-text relationship label by creating a label object and submitting it to the engine.
# This workflow is simple and does not require multi-step state management.
# Returns True if the label was successfully persisted, False otherwise.
def process_image_text_relationship(engine: LabelingEngine, user_name: str, row_id: str, relationship: str) -> bool:
    # Initializes a new ImageTextLabel object with the provided data.
    # Returns an ImageTextLabel instance.
    label = ImageTextLabel(row_id=row_id, labeler_name=user_name, relationship=relationship)
    
    # Submits the finalized label to the engine for filesystem persistence.
    # Returns True if successful, False otherwise.
    return engine.submit_label(user_name, label)


# ===========================================================================
# Workflow B: Entity & Sentiment (Multi-Step Process)
# ===========================================================================

# Initiates the first step of the multi-part Entity-Sentiment workflow.
# It creates a label object and caches it in memory until subsequent steps are completed.
# Returns the newly created and partially populated EntitySentimentLabel object.
def process_entity_identification(user_name: str, row_id: str, entity_name: str, entity_type: str) -> EntitySentimentLabel:
    # Initializes a new EntitySentimentLabel object for the current user and row.
    # Returns an EntitySentimentLabel instance.
    label = EntitySentimentLabel(row_id=row_id, labeler_name=user_name)
    # Sets the entity name and type on the label object.
    # Returns None.
    label.set_entity(entity_name, entity_type)

    # Caches the partial label in a global dictionary to maintain state between API calls.
    # Returns None.
    _pending_entity_labels[(user_name, row_id)] = label
    return label

# Updates an existing pending label with a topic assignment, completing the second step of the workflow.
# It retrieves the label from the in-memory cache using a composite key of user and row.
# Returns the updated EntitySentimentLabel object.
def process_topic_assignment(user_name: str, row_id: str, topic: str) -> EntitySentimentLabel:
    # Generates a composite key from the username and row ID for cache lookup.
    # Returns a tuple.
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        # Raises an error if the user attempts this step without completing the first one.
        # Returns a KeyError.
        raise KeyError("Workflow Error: You must identify an entity (Step 1) before assigning a topic.")

    label = _pending_entity_labels[key]
    # Sets the topic for the entity identified in the previous step.
    # Returns None.
    label.set_topic(topic)
    return label

# Finalizes the multi-step Entity-Sentiment workflow by setting the sentiment and submitting to the engine.
# It also cleans up the in-memory cache upon a successful save to prevent memory leaks.
# Returns True if the full label was successfully persisted, False otherwise.
def process_entity_sentiment(engine: LabelingEngine, user_name: str, row_id: str, sentiment: str) -> bool:
    # Generates a lookup key for the pending label cache.
    # Returns a tuple.
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        # Raises an error if mandatory previous steps are missing.
        # Returns a KeyError.
        raise KeyError("Workflow Error: You must complete identification and topic assignment before sentiment.")

    label = _pending_entity_labels[key]
    # Sets the final sentiment value and marks the label as complete.
    # Returns None.
    label.set_sentiment(sentiment)

    # Submits the fully completed multi-step label to the labeling engine.
    # Returns True if successful, False otherwise.
    success = engine.submit_label(user_name, label)

    if success:
        # Removes the completed label from the pending cache to release memory.
        # Returns None.
        del _pending_entity_labels[key]
    
    return success


# ===========================================================================
# Workflow C: Golden Caption
# ===========================================================================

# Handles the one-step captioning workflow by creating a CaptionLabel and persisting it.
# This workflow is used for tasks that only require a descriptive text input for an image.
# Returns True if the caption was successfully saved, False otherwise.
def process_caption(engine: LabelingEngine, user_name: str, row_id: str, caption: str) -> bool:
    # Initializes a new CaptionLabel object with the user-provided text.
    # Returns a CaptionLabel instance.
    label = CaptionLabel(row_id=row_id, labeler_name=user_name, caption=caption)
    # Delegates the persistence of the caption label to the engine.
    # Returns True or False.
    return engine.submit_label(user_name, label)


# ===========================================================================
# Custom Workflow: Generic field submission
# ===========================================================================

# Processes a custom workflow result by packaging arbitrary field data into a CustomLabel object.
# This allows the system to support new, dynamically defined workflows without backend changes.
# Returns True if the custom label data was successfully persisted, False otherwise.
def process_custom_workflow(engine: LabelingEngine, user_name: str, row_id: str, fields: dict) -> bool:
    # Removes the row_id from the fields dictionary if it was redundantly included by the frontend.
    # Returns the value associated with 'row_id' or None.
    fields.pop("row_id", None)
    # Initializes a CustomLabel with metadata and the dynamic fields dictionary.
    # Returns a CustomLabel instance.
    label = CustomLabel(row_id=row_id, labeler_name=user_name, fields=fields)
    # Submits the custom label to the engine for storage in the master results file.
    # Returns True or False.
    return engine.submit_label(user_name, label)
