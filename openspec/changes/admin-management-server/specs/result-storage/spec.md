## ADDED Requirements

### Requirement: List video metadata
The ResultStorage class SHALL provide a `list_videos()` method that scans the results directory and returns metadata for all processed videos.

#### Scenario: List all videos
- **WHEN** `list_videos()` is called
- **THEN** system returns a sorted list (by updated_at desc) of dicts, each containing bv_id, title, uploader, duration, language, updated_at, and file availability flags (has_transcript, has_translation, has_summary)

#### Scenario: Empty results directory
- **WHEN** results directory has no video subdirectories
- **THEN** system returns an empty list
