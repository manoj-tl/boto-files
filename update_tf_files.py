import os
import re
import logging
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the root directory containing repositories
ROOT_DIR = "zillow_scraper"
NEW_COST_STRING = 'CostString = "XYZ"'
OLD_COST_STRING_PATTERN = r'CostString\s*=\s*"XY"'
IGNORE_COST_STRING_PATTERN = r'CostString\s*=\s*".*"'
TOUCHED_REPOS = {}
JIRA_TICKET = "JIRA-1234"

# Function to update the file
def update_file(file_path, repo_dir):
    global TOUCHED_REPOS

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            lines = file.readlines()
    except Exception as e:
        logging.error(f"Failed to read file {file_path}: {e}")
        return

    updated_lines = []
    inside_variable_block = False
    variable_name = None
    cost_string_updated = False
    file_modified = False

    for line in lines:
        # Check if inside a variable block for base_tags or base_labels
        if re.match(r'variable\s+"(base_tags|base_labels)"', line):
            inside_variable_block = True
            variable_name = re.search(r'"(base_tags|base_labels)"', line).group(1)
            cost_string_updated = False

        if inside_variable_block:
            # Check if the line contains CostString
            if re.search(r"\s*CostString\s*=", line):
                if re.search(OLD_COST_STRING_PATTERN, line):
                    # Update CostString value
                    updated_lines.append(re.sub(OLD_COST_STRING_PATTERN, NEW_COST_STRING, line))
                    cost_string_updated = True
                    file_modified = True
                    TOUCHED_REPOS.setdefault(repo_dir, set()).add(file_path)
                    continue
                elif re.search(IGNORE_COST_STRING_PATTERN, line):
                    # Ignore if CostString has any value
                    updated_lines.append(line)
                    cost_string_updated = True
                    continue

            # Look for the closing brace of the default block
            if re.match(r"\s*}\s*", line) and not cost_string_updated:
                updated_lines.append(f"    {NEW_COST_STRING}\n")
                cost_string_updated = True
                file_modified = True
                TOUCHED_REPOS.setdefault(repo_dir, set()).add(file_path)

        # End of variable block
        if inside_variable_block and re.match(r"\s*}\s*", line):
            inside_variable_block = False
            variable_name = None

        updated_lines.append(line)

    # Write back the updated content if modified
    if file_modified:
        try:
            with open(file_path, "w", encoding="utf-8", errors="replace") as file:
                file.writelines(updated_lines)
                logging.info(f"File updated: {file_path}")
        except Exception as e:
            logging.error(f"Failed to write to file {file_path}: {e}")

# Run Terraform fmt for the touched files
def run_terraform_fmt(touched_files):
    unique_files = list(set(touched_files))  # Deduplicate files
    for file in unique_files:
        try:
            logging.info(f"Running Terraform fmt on {file}")
            subprocess.run(["terraform", "fmt", file], check=True)
            logging.info(f"Terraform fmt succeeded on {file}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Terraform fmt failed on {file}: {e}")

# Traverse the root directory for all files
def process_directory(root_dir):
    for subdir, dirs, files in os.walk(root_dir):
        if ".git" in os.listdir(subdir):
            for dir_name in dirs:
                sub_dir_path = os.path.join(subdir, dir_name)
                for subdir2, _, files2 in os.walk(sub_dir_path):
                    for file in files2:
                        file_path = os.path.join(subdir2, file)
                        update_file(file_path, subdir)
            for file in files:
                file_path = os.path.join(subdir, file)
                update_file(file_path, subdir)

# Execute the script
def main():
    logging.info("Starting script execution")
    process_directory(ROOT_DIR)

    # Print the files that got touched
    logging.info("Files updated:")
    all_touched_files = []
    for repo, files in TOUCHED_REPOS.items():
        logging.info(f"Repository: {repo}")
        for file in files:
            logging.info(f"  {file}")
            all_touched_files.append(file)

    # Run Terraform fmt on each unique touched file
    run_terraform_fmt(all_touched_files)

    logging.info("Script execution completed")

main()
