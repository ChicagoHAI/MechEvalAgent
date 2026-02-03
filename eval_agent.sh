TASK_NAMES=(
    "YOUR_TASK_NAME"
)

for TASK_NAME in "${TASK_NAMES[@]}"; do
    TASK_ID=${TASK_NAME%%_*}
    
    echo "Processing: $TASK_NAME (ID: $TASK_ID)"

    # 3. Construct the prompt paths
    P_BASE="prompts/evaluation/human/${TASK_NAME}"
    PROMPTS="${P_BASE}/code_evaluation.txt,${P_BASE}/consistency_evaluation.txt,${P_BASE}/generalization_test.txt,${P_BASE}/replicator_model.txt,${P_BASE}/instruction_following.txt"

    # 4. Run the command
    bash run_critic.sh \
        --prompts "$PROMPTS" \
        --repo_path "YOUR_PATH/${TASK_NAME}" \
        --tasks "$TASK_ID"

    echo "Finished $TASK_ID"
    echo "------------------------------------------"
done

for TASK_NAME in "${TASK_NAMES[@]}"; do
    TASK_ID=${TASK_NAME%%_*}
    
    echo "Processing: $TASK_NAME (ID: $TASK_ID)"

    # 3. Construct the prompt paths
    P_BASE="prompts/evaluation/human/${TASK_NAME}"
    PROMPTS="${P_BASE}/replicator_evaluator.txt"

    # 4. Run the command
    bash run_critic.sh \
        --prompts "$PROMPTS" \
        --repo_path "YOUR_PATH/${TASK_NAME}" \
        --tasks "$TASK_ID"

    echo "Finished $TASK_ID"
    echo "------------------------------------------"
done
