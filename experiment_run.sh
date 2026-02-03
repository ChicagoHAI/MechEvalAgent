EXP_REPOS=(
    "counting"
    "inevitability"
    "irreversable"
    "moral"
    "multilingual"
    "persona"
    "sarcasm"
    "typo"
    "unanswerable"
    "uncertainty"
)
for EXP_REPO in "${EXP_REPOS[@]}"; do
    bash run_experiment.sh --task-name ${EXP_REPO} --prompts prompts/research_agent_input/open_${EXP_REPO}.txt
done
