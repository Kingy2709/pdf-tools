#!/bin/bash
# sync-pdf-tools-to-notion.sh
# Syncs pdf-tools scripts to Notion Scripts database
# Usage: ./sync-pdf-tools-to-notion.sh

set -euo pipefail

SCRIPTS_DATA_SOURCE_ID="28cca776-b4c9-8162-8251-000be6de7dee"
SCRIPTS_DIR="$HOME/dev/python/pdf-tools"

# Read the JSON file
jq -c '.[]' /tmp/pdf-tools-scripts.json | while read -r script; do
  name=$(echo "$script" | jq -r '.name')
  description=$(echo "$script" | jq -r '.description')
  category=$(echo "$script" | jq -r '.category')
  filepath="$SCRIPTS_DIR/$name"
  
  echo "📝 Syncing: $name"
  
  # Check if script exists in Notion
  existing=$(curl -s -X POST "https://api.notion.com/v1/data_sources/$SCRIPTS_DATA_SOURCE_ID/query" \
    -H "Authorization: Bearer $NOTION_API_KEY" \
    -H "Notion-Version: 2025-09-03" \
    -H "Content-Type: application/json" \
    -d "{
      \"filter\": {
        \"property\": \"Script Name\",
        \"title\": {
          \"equals\": \"$name\"
        }
      }
    }" | jq -r '.results[0].id // empty')
  
  if [ -n "$existing" ]; then
    echo "  ⚠️  Already exists, skipping..."
    continue
  fi
  
  # Create new entry
  curl -s -X POST https://api.notion.com/v1/pages \
    -H "Authorization: Bearer $NOTION_API_KEY" \
    -H "Notion-Version: 2025-09-03" \
    -H "Content-Type: application/json" \
    -d "{
      \"parent\": {
        \"data_source_id\": \"$SCRIPTS_DATA_SOURCE_ID\"
      },
      \"properties\": {
        \"Script Name\": {
          \"title\": [
            {
              \"text\": {
                \"content\": \"$name\"
              }
            }
          ]
        },
        \"File Path\": {
          \"rich_text\": [
            {
              \"text\": {
                \"content\": \"$filepath\"
              }
            }
          ]
        },
        \"Description\": {
          \"rich_text\": [
            {
              \"text\": {
                \"content\": \"[$category] $description\"
              }
            }
          ]
        },
        \"Script Status\": {
          \"status\": {
            \"name\": \"Active\"
          }
        }
      }
    }" > /dev/null
  
  echo "  ✅ Created"
  sleep 0.3  # Rate limit protection
done

echo ""
echo "🎉 Sync complete!"
