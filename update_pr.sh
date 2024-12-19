#!/bin/bash

# Define the root directory containing repositories
ROOT_DIR="./" # Adjust this if needed
COST_STRING_ENTRY='CostString = "XYZ"'

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

    # Check if the file contains the base_tags variable map
    if grep -q "base_tags" "$FILE"; then
      echo "    Found 'base_tags' in $FILE"

      # Check if CostString already exists within base_tags
      if grep -q "$COST_STRING_ENTRY" "$FILE"; then
        echo "    'CostString' already exists in base_tags in $FILE"
      else
        echo "    Adding 'CostString' to base_tags in $FILE"
        # Add CostString to base_tags using sed
        sed -i '/base_tags[[:space:]]*{/,/}/ s/}/  CostString = "XYZ"\n}/' "$FILE"
      fi
    fi
  done
done

echo "Script completed."
