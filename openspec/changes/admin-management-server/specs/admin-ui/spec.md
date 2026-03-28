## ADDED Requirements

### Requirement: Video list display
The system SHALL provide a web page at `/admin/` that displays all processed videos in a table format with BV ID, title, uploader, duration, language, and processing timestamp.

#### Scenario: List all videos
- **WHEN** user accesses `/admin/`
- **THEN** system displays a table of all videos found in the results directory

#### Scenario: Empty results
- **WHEN** no videos have been processed yet
- **THEN** system displays an empty state message

### Requirement: Video search
The system SHALL allow users to search videos by title or uploader name via a query parameter on the list page.

#### Scenario: Search by title
- **WHEN** user enters a search term in the search box and submits
- **THEN** system filters the video list to show only videos whose title or uploader contains the search term (case-insensitive)

#### Scenario: Clear search
- **WHEN** user clears the search box and submits
- **THEN** system displays all videos

### Requirement: Video detail view
The system SHALL provide a web page at `/admin/video/{bv_id}` that displays the full processing results for a single video, including transcript, translation (if available), cleaned transcript, summary, and audio player.

#### Scenario: View video with translation
- **WHEN** user clicks on a video in the list
- **THEN** system displays transcript, translation, cleaned transcript, summary, and audio player

#### Scenario: View video without translation
- **WHEN** user views a Chinese-language video
- **THEN** system displays transcript, cleaned transcript, summary, and audio player (no translation section)

#### Scenario: Video not found
- **WHEN** user accesses a BV ID that does not exist in results
- **THEN** system returns a 404 error page

### Requirement: Audio playback
The system SHALL allow users to play the audio file directly in the browser via an HTML5 audio player.

#### Scenario: Play audio
- **WHEN** user is on the video detail page
- **THEN** system displays an audio player that can play the video's audio.wav file

### Requirement: Delete video results
The system SHALL allow users to delete all files for a video via a POST action on the detail page.

#### Scenario: Confirm and delete
- **WHEN** user clicks the delete button and confirms
- **THEN** system removes the entire directory for that BV ID and redirects to the list page

### Requirement: Reprocess video
The system SHALL allow users to re-trigger the processing pipeline for an existing video via a POST action on the detail page.

#### Scenario: Trigger reprocess
- **WHEN** user clicks the reprocess button
- **THEN** system starts reprocessing the video in the background and shows a confirmation message

#### Scenario: Reprocess completion
- **WHEN** background reprocessing finishes
- **THEN** updated results are available on the detail page on next visit

## MODIFIED Requirements

### Requirement: List video metadata
The ResultStorage class SHALL provide a method to scan the results directory and return metadata for all processed videos.

#### Scenario: List all videos
- **WHEN** `list_videos()` is called
- **THEN** system returns a list of dicts, each containing bv_id, title, uploader, duration, language, updated_at, and file availability flags
