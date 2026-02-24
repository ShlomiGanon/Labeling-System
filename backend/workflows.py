"""
workflows.py
------------
This file contains the logic for the different labeling tasks (Workflows).

We have 3 main ways to label:
A. Image-Text Relationship: A simple 1-step choice.
B. Entity Sentiment: A 3-step process (Identify entity -> Choose topic -> Set sentiment).
C. Golden Caption: A simple 1-step where the user writes a description.
"""

from models import ImageTextLabel, EntitySentimentLabel, CaptionLabel
from labeling_engine import LabelingEngine

# This dictionary stores labels that are "in progress" (for 3-step tasks)
_pending_entity_labels: dict = {}

# ===========================================================================
# Workflow A: Image-Text Relationship
# ===========================================================================

def process_image_text_relationship(engine: LabelingEngine, user_name: str, row_id: str, relationship: str) -> bool:
    """
    Workflow A: Save a simple relationship label.
    """
    label = ImageTextLabel(row_id=row_id, labeler_name=user_name, relationship=relationship)
    
    # Send it to the engine to save it
    return engine.submit_label(user_name, label)


# ===========================================================================
# Workflow B: Entity & Sentiment (3 Steps)
# ===========================================================================

def process_entity_identification(user_name: str, row_id: str, entity_name: str, entity_type: str) -> EntitySentimentLabel:
    """
    Step 1: Start a new sentiment label by identifying the entity.
    """
    label = EntitySentimentLabel(row_id=row_id, labeler_name=user_name)
    label.set_entity(entity_name, entity_type)

    # Store it in memory for now (don't save to file yet!)
    _pending_entity_labels[(user_name, row_id)] = label
    return label

def process_topic_assignment(user_name: str, row_id: str, topic: str) -> EntitySentimentLabel:
    """
    Step 2: Assign a topic to the label we started in Step 1.
    """
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        raise KeyError("You must do Step 1 first!")

    label = _pending_entity_labels[key]
    label.set_topic(topic)
    return label

def process_entity_sentiment(engine: LabelingEngine, user_name: str, row_id: str, sentiment: str) -> bool:
    """
    Step 3: Set the sentiment and save the whole thing to the file.
    """
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        raise KeyError("You must do Step 1 and 2 first!")

    label = _pending_entity_labels[key]
    label.set_sentiment(sentiment)

    # Now we can finally save it!
    success = engine.submit_label(user_name, label)

    # If it saved okay, remove it from our "pending" list
    if success:
        del _pending_entity_labels[key]
    
    return success


# ===========================================================================
# Workflow C: Golden Caption
# ===========================================================================

def process_caption(engine: LabelingEngine, user_name: str, row_id: str, caption: str) -> bool:
    """
    Workflow C: Save a caption written by the user.
    """
    label = CaptionLabel(row_id=row_id, labeler_name=user_name, caption=caption)
    return engine.submit_label(user_name, label)
