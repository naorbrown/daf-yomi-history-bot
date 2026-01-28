#!/bin/bash
# Ralph Wiggum - AI Loop Technique for Claude Code
set -e

MAX_ITERATIONS=50
COMPLETION_PROMISE="COMPLETE"
PROMPT_FILE=""
WORKING_DIR="."
MODEL=""
VERBOSE=false
DRY_RUN=false
TASK_PROMPT=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

while [[ $# -gt 0 ]]; do
    case $1 in
            --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
                    --completion-promise) COMPLETION_PROMISE="$2"; shift 2 ;;
                            --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
                                    --working-dir) WORKING_DIR="$2"; shift 2 ;;
                                            --model) MODEL="$2"; shift 2 ;;
                                                    --verbose) VERBOSE=true; shift ;;
                                                            --dry-run) DRY_RUN=true; shift ;;
                                                                    --help|-h)
                                                                                echo "Ralph Wiggum - AI Loop Technique"
                                                                                            echo "Usage: $0 [options] \"prompt\""
                                                                                                        echo "  --max-iterations N    (default: 50)"
                                                                                                                    echo "  --completion-promise  (default: COMPLETE)"
                                                                                                                                echo "  --prompt-file FILE"
                                                                                                                                            echo "  --verbose, --dry-run, --model MODEL"
                                                                                                                                                        exit 0 ;;
                                                                                                                                                                *) TASK_PROMPT="$1"; shift ;;
                                                                                                                                                                    esac
                                                                                                                                                                    done
                                                                                                                                                                    
                                                                                                                                                                    get_prompt() {
                                                                                                                                                                        if [[ -n "$PROMPT_FILE" ]] && [[ -f "$PROMPT_FILE" ]]; then cat "$PROMPT_FILE"
                                                                                                                                                                            elif [[ -n "$TASK_PROMPT" ]]; then echo "$TASK_PROMPT"
                                                                                                                                                                                else echo -e "${RED}Error: No prompt${NC}" >&2; exit 1; fi
                                                                                                                                                                                }
                                                                                                                                                                                
                                                                                                                                                                                main() {
                                                                                                                                                                                    local prompt=$(get_prompt)
                                                                                                                                                                                        local cmd="claude"; [[ -n "$MODEL" ]] && cmd="$cmd --model $MODEL"; cmd="$cmd -p"
                                                                                                                                                                                            
                                                                                                                                                                                                echo -e "${PURPLE}=== Ralph Wiggum ===${NC}"
                                                                                                                                                                                                    [[ "$DRY_RUN" == true ]] && { echo "[DRY RUN] $cmd"; exit 0; }
                                                                                                                                                                                                        
                                                                                                                                                                                                            cd "$WORKING_DIR"
                                                                                                                                                                                                                local i=0
                                                                                                                                                                                                                    while [[ $i -lt $MAX_ITERATIONS ]]; do
                                                                                                                                                                                                                            i=$((i + 1))
                                                                                                                                                                                                                                    [[ "$VERBOSE" == true ]] && echo -e "${BLUE}--- Iteration $i ---${NC}"
                                                                                                                                                                                                                                            local out=$(echo "$prompt" | $cmd 2>&1) || true
                                                                                                                                                                                                                                                    echo "$out"
                                                                                                                                                                                                                                                            echo "$out" | grep -q "$COMPLETION_PROMISE" && { echo -e "${GREEN}=== COMPLETE ===${NC}"; exit 0; }
                                                                                                                                                                                                                                                                    sleep 1
                                                                                                                                                                                                                                                                        done
                                                                                                                                                                                                                                                                         #!/bin/bash
                                                                                                                                                                                                                                                                         # Ralph Wiggum - AI Loop Technique for Claude Code
                                                                                                                                                                                                                                                                         set -e
                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                         MAX_ITERATIONS=50
                                                                                                                                                                                                                                                                         COMPLETION_PROMISE="COMPLETE"
                                                                                                                                                                                                                                                                         PROMPT_FILE=""
                                                                                                                                                                                                                                                                         WORKING_DIR="."
                                                                                                                                                                                                                                                                         MODEL=""
                                                                                                                                                                                                                                                                         VERBOSE=false
                                                                                                                                                                                                                                                                         DRY_RUN=false
                                                                                                                                                                                                                                                                         TASK_PROMPT=""
                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                         RED='\033[0;31m'
                                                                                                                                                                                                                                                                         GREEN='\033[0;32m'
                                                                                                                                                                                                                                                                         YELLOW='\033[1;33m'
                                                                                                                                                                                                                                                                         BLUE='\033[0;34m'
                                                                                                                                                                                                                                                                         PURPLE='\033[0;35m'
                                                                                                                                                                                                                                                                         NC='\033[0m'
                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                         while [[ $# -gt 0 ]]; do
                                                                                                                                                                                                                                                                             case $1 in
                                                                                                                                                                                                                                                                                     --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
                                                                                                                                                                                                                                                                                             --completion-promise) COMPLETION_PROMISE="$2"; shift 2 ;;
                                                                                                                                                                                                                                                                                                     --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
                                                                                                                                                                                                                                                                                                             --working-dir) WORKING_DIR="
