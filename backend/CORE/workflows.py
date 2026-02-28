# Workflow helpers for the supported labeling flows.

from typing import Dict, Tuple
from models import (
    ImageTextLabel,
    EntitySentimentLabel,
    CaptionLabel,
    CustomLabel,
    ImageTextRelationship,
    EntityType,
    Sentiment,
)
from labeling_engine import LabelingEngine

# Keep partial Workflow B data until the final step is submitted.
_pending_entity_labels: Dict[Tuple[str, str], EntitySentimentLabel] = {}


# One-step workflow.
def process_image_text_relationship(
    engine: LabelingEngine,
    user_name: str,
    row_id: str,
    relationship: str,
) -> bool:
    label = ImageTextLabel(row_id=row_id, labeler_name=user_name, relationship=relationship)
    return engine.submit_label(user_name, label)


# Step 1 of the multi-step entity workflow.
def process_entity_identification(
    user_name: str,
    row_id: str,
    entity_name: str,
    entity_type: str,
) -> EntitySentimentLabel:
    label = EntitySentimentLabel(row_id=row_id, labeler_name=user_name)
    label.set_entity(entity_name, entity_type)
    _pending_entity_labels[(user_name, row_id)] = label
    return label


# Step 2 of the multi-step entity workflow.
def process_topic_assignment(user_name: str, row_id: str, topic: str) -> EntitySentimentLabel:
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        raise KeyError("Workflow Error: You must identify an entity (Step 1) before assigning a topic.")

    label = _pending_entity_labels[key]
    label.set_topic(topic)
    return label


# Final step of the multi-step entity workflow.
def process_entity_sentiment(engine: LabelingEngine, user_name: str, row_id: str, sentiment: str) -> bool:
    key = (user_name, row_id)
    if key not in _pending_entity_labels:
        raise KeyError("Workflow Error: You must complete identification and topic assignment before sentiment.")

    label = _pending_entity_labels[key]
    label.set_sentiment(sentiment)
    success = engine.submit_label(user_name, label)

    if success:
        del _pending_entity_labels[key]

    return success


# One-step caption workflow.
def process_caption(engine: LabelingEngine, user_name: str, row_id: str, caption: str) -> bool:
    label = CaptionLabel(row_id=row_id, labeler_name=user_name, caption=caption)
    return engine.submit_label(user_name, label)


# Save a custom workflow payload as-is.
def process_custom_workflow(engine: LabelingEngine, user_name: str, row_id: str, fields: dict) -> bool:
    fields.pop("row_id", None)
    label = CustomLabel(row_id=row_id, labeler_name=user_name, fields=fields)
    return engine.submit_label(user_name, label)
