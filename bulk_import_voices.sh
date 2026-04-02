#!/bin/bash
# =============================================================================
# Bulk Voice Import — Upload 300+ voice files to FrenzAI
# =============================================================================
# Usage:
#   1. Copy all voice files (.opus, .wav, .mp3, .flac, .ogg, .m4a) into:
#      data/voices/import/
#
#   2. Run: bash bulk_import_voices.sh
#
#   This will:
#   - Copy all files to staging
#   - Auto-detect gender (Male/Female) via pitch analysis
#   - Auto-trim to center 60 seconds (files >60s)
#   - Convert to mono WAV 44.1kHz
#   - Add all voices to the database
#   - Name them as "Male Voice 1", "Female Voice 2", etc.
# =============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMPORT_DIR="$PROJECT_DIR/data/voices/import"
API_URL="${FRENZAI_API:-http://127.0.0.1:8111}"

echo "============================================"
echo "  FrenzAI Bulk Voice Import"
echo "============================================"

# Count files
FILE_COUNT=$(find "$IMPORT_DIR" -type f \( -name "*.opus" -o -name "*.wav" -o -name "*.mp3" -o -name "*.flac" -o -name "*.ogg" -o -name "*.m4a" \) 2>/dev/null | wc -l)

if [ "$FILE_COUNT" -eq 0 ]; then
    echo "No audio files found in $IMPORT_DIR"
    echo "Supported formats: .opus, .wav, .mp3, .flac, .ogg, .m4a"
    exit 1
fi

echo "Found $FILE_COUNT voice files in $IMPORT_DIR"
echo ""

# Check if backend is running
if ! curl -s "$API_URL/api/health" > /dev/null 2>&1; then
    echo "ERROR: FrenzAI backend is not running at $API_URL"
    echo "Start it first: systemctl start frenzai"
    exit 1
fi

echo "Backend is running at $API_URL"
echo ""

# Step 1: Import all to staging via API
echo "[1/2] Importing files to staging..."
RESULT=$(curl -s -X POST "$API_URL/api/narrator-voices/import-all")
IMPORTED=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('imported',0))" 2>/dev/null || echo "0")
FAILED=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('failed',0))" 2>/dev/null || echo "0")

echo "  Staged: $IMPORTED files"
if [ "$FAILED" -gt 0 ]; then
    echo "  Failed: $FAILED files"
fi

# Step 2: Get staged files and add them all as voices
echo "[2/2] Adding voices to database (with trim + gender detection)..."

# Get all staged files
STAGED=$(curl -s "$API_URL/api/clone/staged")
STAGED_COUNT=$(echo "$STAGED" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [ "$STAGED_COUNT" -eq 0 ]; then
    echo "  No staged files found. Import may have failed."
    exit 1
fi

echo "  $STAGED_COUNT files staged, adding to database..."

# Build the add-voices payload
PAYLOAD=$(echo "$STAGED" | python3 -c "
import json, sys
staged = json.load(sys.stdin)
voices = []
for i, s in enumerate(staged, 1):
    gender = s.get('gender', 'Male')
    name = f'{gender} Voice {i}'
    voices.append({
        'stage_id': s['stage_id'],
        'name': name,
        'engine': 'chatterbox',
        'language': 'en',
    })
print(json.dumps(voices))
")

RESULT=$(curl -s -X POST "$API_URL/api/clone/add-voices" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

ADDED=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null || echo "0")
ADD_FAILED=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('failed',0))" 2>/dev/null || echo "0")

echo ""
echo "============================================"
echo "  Import Complete!"
echo "============================================"
echo "  Added: $ADDED voices"
if [ "$ADD_FAILED" -gt 0 ]; then
    echo "  Failed: $ADD_FAILED"
fi
echo ""
echo "  Voices are ready in FrenzAI!"
echo "  Open $API_URL and go to Voices page."
echo ""
