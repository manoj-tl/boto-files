#!/bin/bash

# Define the root directory containing repositories
ROOT_DIR="./" # Adjust this if needed
OLD_COST_STRING='XY'
NEW_COST_STRING='XYZ'

# Find all directories containing `.git` (repositories)
REPOS=$(find "$ROOT_DIR" -type d -name ".git" | xargs -n 1 dirname)

# Loop through each repository
for REPO in $REPOS; do
  echo "Processing repository: $REPO"

  # Find all Terraform files in the repository
  TF_FILES=$(find "$REPO" -type f -name "*.tf")

  # Loop through each Terraform file
  for FILE in $TF_FILES; do
    echo "  Checking file: $FILE"

    # Process for both base_tags and base_labels
    for VAR_NAME in "base_tags" "base_labels"; do
      # Check if the file contains the variable
      if grep -q 'variable "'$VAR_NAME'".*default.*{' "$FILE"; then
        echo "    Found '$VAR_NAME' variable in $FILE"

        # First scenario: Check if CostString exists with value 'XY'
        if grep -q '[[:space:]]*CostString[[:space:]]*=[[:space:]]*"XY"' "$FILE"; then
          echo "    Found CostString with value 'XY', updating to '$NEW_COST_STRING' in $VAR_NAME"
          sed -i.bak 's/\([[:space:]]*CostString[[:space:]]*=[[:space:]]*\)"XY"/\1"'"$NEW_COST_STRING"'"/' "$FILE"
        
        # Second scenario: Check if CostString doesn't exist at all
        elif ! grep -q '[[:space:]]*CostString[[:space:]]*=' "$FILE"; then
          echo "    No CostString found, adding new entry to $VAR_NAME"
          sed -i.bak '/variable "'$VAR_NAME'".*default[[:space:]]*=[[:space:]]*{/,/}/{s/}/  CostString = "'"$NEW_COST_STRING"'"\n}/}' "$FILE"
        
        else
          echo "    CostString exists with different value in $VAR_NAME, skipping update"
        fi

        # Remove backup if operation was successful
        if [ $? -eq 0 ]; then
          rm -f "${FILE}.bak"
        fi
      fi
    done
  done
done

echo "Script completed."