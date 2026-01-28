# Daf Yomi History Bot - Claude Code Instructions

## Project Overview
Telegram bot providing historical context for Daf Yomi. Uses Ralph Wiggum technique for iterative development.

## Tech Stack
- Python with python-telegram-bot
- - Serverless deployment
  - - CI/CD via GitHub Actions
   
    - ## Development Workflow
   
    - ### Using Ralph Wiggum Loop
    - ```bash
      ./ralph.sh "Your task. Output COMPLETE when done." --max-iterations 20
      ./ralph.sh --prompt-file prompts/feature.md --verbose
      ```

      ### Key Principles
      1. Clear completion criteria in all prompts
      2. 2. Break large tasks into phases
         3. 3. Always use --max-iterations as safety net
           
            4. ## Testing
            5. ```bash
               pytest tests/ -v
               ```

               ## Completion Signals
               - `<promise>COMPLETE</promise>` - Task finished
               - - `<promise>BLOCKED</promise>` - Needs human input
