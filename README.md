# Labeling UI 🚀

A lightweight, mobile-responsive web app for high-speed multi-modal data annotation and entity-level sentiment analysis.

## 🎯 Key Features
* **Mobile-First:** Optimized for swipe/quick-tap labeling on the go.
* **State Management:** Tracks "Last Labeled Index" to prevent data collision.
* **Cloud Integration:** Reads from Source CSV; serves assets from S3/Google-Drive.
* **Dynamic Tasks:** Supports multiple user-defined labeling workflows.

## 🛠 Workflows
1. **Workflow A (Multi-modal):** Image-Text relationship (Independent, Context-Dependent, Noise).
2. **Workflow B (Entity-Centric):** Entity ID → Topic Assignment → Sentiment/Emotion rating.
3. **Workflow C (Captioning):** Free-text entry for "Golden Captions".
