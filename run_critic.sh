#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────
# 0) Parse command line arguments and set defaults
# ───────────────────────────────────────────────

# Define the prompts (defaults)
CIRCUIT_PROMPTS=("prompts/icot/code_evaluation.txt")
TASK_NAME=("function_vector")
REPO_PATH=("YOUR_PATH/function_vectors_eval")

PROVIDERS="claude"  # Default to claude only
CONCURRENT_LIMIT=3  # Default concurrent sessions
PUSH_TO_BRANCH=false  # Default: don't push to git
HELP_MESSAGE="Usage: $0 [OPTIONS]
Options:
  --prompts PROMPTS        Comma-separated list of prompt files [default: 4 evaluation prompts]
  --providers PROVIDERS    Comma-separated list of providers (claude,gemini,codex) [default: claude]
  --concurrent LIMIT       Max concurrent sessions per provider [default: 3]
  --tasks TASK_NAME        Task name [default: ioi]
  --repo_path REPO_PATH    Path to the repository [default: net/scratch2/smallyan/function_vectors_eval]
  --push                   Create a git branch and push results [default: false]
  --help                   Show this help message

Examples:
  $0                                                          # Run with defaults
  $0 --providers claude,gemini                                # Run with multiple providers
  $0 --prompts prompts/task/eval1.txt,prompts/task/eval2.txt  # Run with custom prompts
  $0 --prompts prompts/task/eval1.txt --providers claude      # Combine options
  $0 --tasks function_vector
  $0 --repo_path
  $0 --push                                                   # Push results to new git branch
  $0 --providers gemini --concurrent 2                        # Run with gemini, max 2 concurrent"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prompts)
            IFS=',' read -ra CIRCUIT_PROMPTS <<< "$2"
            shift 2
            ;;
        --providers)
            PROVIDERS="$2"
            shift 2
            ;;
        --concurrent)
            CONCURRENT_LIMIT="$2"
            shift 2
            ;;
        --tasks)
            TASK_NAME="$2"
            shift 2
            ;;
        --repo_path)
            REPO_PATH="$2"
            shift 2
            ;;
        --push)
            PUSH_TO_BRANCH=true
            shift
            ;;
        --help)
            echo "$HELP_MESSAGE"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "$HELP_MESSAGE"
            exit 1
            ;;
    esac
done

# Convert providers string to array
IFS=',' read -ra PROVIDER_ARRAY <<< "$PROVIDERS"

# source "$(dirname "$0")/venv/bin/activate"
export DISABLE_AUTOUPDATER=1
# ───────────────────────────────────────────────

###############################################################################
# 1) cleanup trap
###############################################################################

cleanup() {
    echo ""
    echo "▶ Stopping any running scribe copilot processes..."
    pkill -f "scribe copilot" || true
    # Clean up marker file
    rm -f "/tmp/scribe_run_start_${RUN_TIMESTAMP}" 2>/dev/null || true
    echo "✔ Cleanup complete."
}
# Run cleanup when the script exits *for any reason* (normal exit, Ctrl-C, Ctrl-\,
# errors if set -e, etc.)
trap cleanup EXIT INT TERM

###############################################################################
# 2) Note: Modern scribe auto-manages servers via MCP
###############################################################################
# Note: scribe copilot automatically manages Jupyter servers via MCP
# Each session gets its own auto-managed server (no manual port coordination needed)

###############################################################################
# 3) organize prompts by subsection and create run directory
###############################################################################
# Create timestamp-based run directory for this session
ROOT_DIR=$(pwd)
RUN_TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
PROVIDER_LIST=$(echo "$PROVIDERS" | tr ',' '-')
RUN_DIR="YOUR_PATH/new_eval_agent_logs/${TASK_NAME}_${PROVIDER_LIST}_${RUN_TIMESTAMP}"
mkdir -p "$RUN_DIR"/{logs,notebooks,results}
mkdir -p logs

echo "🚀 Starting circuits benchmark with providers: $PROVIDERS"
echo "📁 Results will be saved to: $RUN_DIR"

# Create marker file to track when this run started (for notebook organization)
touch "/tmp/scribe_run_start_${RUN_TIMESTAMP}"

# Export run directory for child processes to use
export SCRIBE_BENCHMARK_RUN_DIR="$RUN_DIR"

###############################################################################
# 4) Run circuit tasks with port rotation
###############################################################################

echo "▶ Running circuit tasks concurrently..."

# Note: Port management functions removed - modern scribe auto-manages servers

# Function to run a single circuit task using copilot mode
run_circuit_task() {
    local prompt_file=$1
    local provider=$2
    local prompt_name=$(basename "$prompt_file" .txt)
    
    echo "  ▶ Running $prompt_name with $provider"
    
    # Create a temporary script file for the prompt
    temp_script="/tmp/scribe_prompt_${prompt_name}_${provider}_$$.txt"
    
    # Read the prompt file and create a script that starts a session and runs the task
    {
        echo "Start a new session for circuit analysis"
        echo ""
        echo "IMPORTANT: Before starting, set up the correct working directory by running:"
        echo "import os"
        echo "os.chdir('$ROOT_DIR')"
        echo ""
        echo "Please execute the following task:"
        echo ""
        cat "$prompt_file"
        echo ""
        echo "You should use GPU compute if available by checking if 'cuda' is available."
        echo ""
        echo "Please complete this task and save your results. DO NOT resume the session in the same notebook, create a new session to continue the task."
    } > "$temp_script"
    
    # Run the task using scribe with specific provider. I remove the time out timeout 2300
    { cat "$temp_script"; echo; } | \
    stdbuf -oL -eL env PYTHONUNBUFFERED=1 SCRIBE_BENCHMARK_RUN_DIR="$RUN_DIR"  \
        scribe "$provider" --dangerously-skip-permissions > "$RUN_DIR/logs/${prompt_name}_${provider}.log" 2>&1
    
    # Clean up temporary file
    rm -f "$temp_script"
    
    echo "  ✔ Completed $prompt_name with $provider"
}

# Create task combinations (prompt + provider pairs)
declare -a task_queue=()
for prompt in "${CIRCUIT_PROMPTS[@]}"; do
    for provider in "${PROVIDER_ARRAY[@]}"; do
        task_queue+=("$prompt:$provider")
    done
done

declare -a running_pids=()   # Array of PIDs for running tasks
total_tasks=${#task_queue[@]}
completed_tasks=0

echo "📋 Total tasks: $total_tasks (${#CIRCUIT_PROMPTS[@]} prompts × ${#PROVIDER_ARRAY[@]} providers)"

# Start initial tasks (up to CONCURRENT_LIMIT per provider, but max overall limit)
max_concurrent=$((CONCURRENT_LIMIT * ${#PROVIDER_ARRAY[@]}))
initial_tasks=$((max_concurrent < total_tasks ? max_concurrent : total_tasks))

for ((i=0; i<initial_tasks; i++)); do
    if [[ ${#task_queue[@]} -gt 0 ]]; then
        task="${task_queue[0]}"
        prompt_file="${task%:*}"
        provider="${task#*:}"
        
        if [[ -f "$prompt_file" ]]; then
            echo "  🚀 Starting task $(basename "$prompt_file" .txt) with $provider ($((i+1))/$initial_tasks)"
            run_circuit_task "$prompt_file" "$provider" &
            task_pid=$!
            running_pids+=("$task_pid")
            task_queue=("${task_queue[@]:1}")  # Remove first element
        else
            echo "  ⚠ Warning: $prompt_file not found"
            task_queue=("${task_queue[@]:1}")  # Remove first element
        fi
    fi
done

# Main loop: monitor running tasks and start new ones when slots become available
while [[ ${#task_queue[@]} -gt 0 ]] || [[ ${#running_pids[@]} -gt 0 ]]; do
    # Check which tasks have completed
    if [[ ${#running_pids[@]} -gt 0 ]]; then
        for i in "${!running_pids[@]}"; do
            pid="${running_pids[$i]}"
            
            if ! kill -0 "$pid" 2>/dev/null; then
                completed_tasks=$((completed_tasks + 1))
                echo "  ✅ Task completed ($completed_tasks/$total_tasks)"
                # Remove from array (this is a bit tricky with regular arrays)
                running_pids=("${running_pids[@]:0:$i}" "${running_pids[@]:$((i+1))}")
                break  # Exit the loop since array indices have changed
            fi
        done
    fi
    
    # Start new tasks if we have available slots
    while [[ ${#task_queue[@]} -gt 0 ]] && [[ ${#running_pids[@]} -lt $max_concurrent ]]; do
        task="${task_queue[0]}"
        prompt_file="${task%:*}"
        provider="${task#*:}"
        
        if [[ -f "$prompt_file" ]]; then
            echo "  🚀 Starting new task $(basename "$prompt_file" .txt) with $provider"
            run_circuit_task "$prompt_file" "$provider" &
            task_pid=$!
            running_pids+=("$task_pid")
            task_queue=("${task_queue[@]:1}")  # Remove first element
        else
            echo "  ⚠ Warning: $prompt_file not found"
            task_queue=("${task_queue[@]:1}")  # Remove first element
        fi
    done
    
    # If we still have tasks running, wait a bit
    if [[ ${#running_pids[@]} -gt 0 ]]; then
        echo "  ⏳ ${#running_pids[@]} tasks running, ${#task_queue[@]} remaining in queue... ($completed_tasks/$total_tasks completed)"
        sleep 30
    fi
done

echo "  🎉 All circuit tasks completed!"



###############################################################################
# 5) organize output files and evaluate results
###############################################################################
echo "▶ Organizing output files…"

# Move scattered JSON files to the results directory
# Files may have provider-specific names now
for file in circuit_*.json real_circuits_*.json *_claude_*.json *_gemini_*.json *_codex_*.json *.png; do
    if [[ -f "$file" ]]; then
        mv "$file" "$RUN_DIR/results/"
        echo "  ✔ Moved $file to $RUN_DIR/results/"
    fi
done

for file in logs/*.md; do
    if [[ -f "$file" ]]; then
        mv "$file" "$RUN_DIR/logs/"
        echo "  ✔ Moved $file to $RUN_DIR/logs/"
    fi
done

for file in logs/*.png; do
    if [[ -f "$file" ]]; then
        mv "$file" "$RUN_DIR/results/"
        echo "  ✔ Moved $file to $RUN_DIR/results/"
    fi
done

for file in notebooks/*.ipynb; do
    if [[ -f "$file" ]]; then
        mv "$file" "$RUN_DIR/notebooks/"
        echo "  ✔ Moved $file to $RUN_DIR/notebooks/"
    fi
done

# Move notebooks from the main notebooks directory to our run-specific directory
# Find notebooks created during this run (using more precise timestamp matching)
# Look for notebooks created after the run started (using find with -newer)
if [[ -f "/tmp/scribe_run_start_${RUN_TIMESTAMP}" ]]; then
    find notebooks/ -name "*.ipynb" -newer "/tmp/scribe_run_start_${RUN_TIMESTAMP}" -exec mv {} "$RUN_DIR/notebooks/" \; 2>/dev/null || true
else
    # Fallback: use date-based matching but be more specific
    find notebooks/ -name "*$(date +%Y-%m-%d-%H)*" -name "*.ipynb" -exec mv {} "$RUN_DIR/notebooks/" \; 2>/dev/null || true
fi


echo "✔ Evaluations complete! Results saved to $RUN_DIR/"
echo "▶ Run summary:"
echo "  🤖 Providers tested: $PROVIDERS"
echo "  📊 Total tasks completed: $total_tasks"
echo "  📁 Logs: $RUN_DIR/logs/"
echo "  📔 Notebooks: $RUN_DIR/notebooks/"
echo "  📊 Results: $RUN_DIR/results/"

# mkdir -p "$REPO_PATH"/eval_logs
# cp -r "$RUN_DIR" "$REPO_PATH"/eval_logs

###############################################################################
# 6) Push to git branch if requested
###############################################################################
if [[ "$PUSH_TO_BRANCH" == "true" ]]; then
    echo "▶ Creating git branch and pushing results..."

    # Create a unique branch name with timestamp
    BRANCH_NAME="evaluation-results-${RUN_TIMESTAMP}"

    # Check if we're in a git repo
    if git rev-parse --git-dir > /dev/null 2>&1; then
        # Create and checkout new branch
        git checkout -b "$BRANCH_NAME"

        # Add the results
        git add "$RUN_DIR"

        # Commit the changes
        git commit -m "Add evaluation results from ${RUN_TIMESTAMP}

Providers: ${PROVIDERS}
Tasks completed: ${total_tasks}
Results directory: ${RUN_DIR}
"

        # Push to remote
        git push -u origin "$BRANCH_NAME"

        echo "✔ Results pushed to branch: $BRANCH_NAME"
    else
        echo "⚠ Not a git repository. Skipping git push."
    fi
fi
