# EPUB to Text & Audio Joiner

This project contains tools to extract text from EPUB files and merge generated audio files (like AI TTS audio or recorded audio) into single audiobook files.

## Files
- `extractor.py`: Extracts text content from EPUB files. Use this to prepare texts for audio generation.
- `audio_joiner.py`: Merges multiple audio files (e.g. `.mp3`, `.m4a`, `.wav`) for a specific book into a single audiobook mp3 file using `ffmpeg`. 
  - Automatically handles different audio formats and recompresses non-mp3 files to `libmp3lame` `.mp3` format.

## Requirements
- Python 3.x
- `ffmpeg` (Required for `audio_joiner.py`)

## Usage

### 1. Audio Joiner
Place your audio files in `output/[Book Name]/audio/`.

To merge them:
```bash
python3 audio_joiner.py "Book Name"
```
The script will automatically scan for `.mp3`, `.m4a`, and `.wav` formats and combine them into `[Book Name].mp3`. You can modify `order.txt` in the audio folder if you wish to adjust the joining order manually.
