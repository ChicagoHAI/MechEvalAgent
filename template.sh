TASK_NAMES=(
    "YOUR_TASK_NAME"
)


for TASK_NAME in "${TASK_NAMES[@]}"; do
    TASK_ID=${TASK_NAME%%_*}
    
    echo "Processing: $TASK_NAME (ID: $TASK_ID)"


    replication=false
    student=false
    human=false
    task_name=${TASK_NAME}
    task_id=${TASK_ID}
    repo_path="YOUR_PATH/open_question/$task_name"
    # documentation_path="YOUR_PATH/$task_name/documentation.pdf"
    replication_path="YOUR_PATH/$task_name/evaluation/replications"
    system_prompt_path="/home/smallyan/eval_agent/prompts/research_agent_input/open_$task_id.txt"

    if $replication; then
        python evaluation_prompt_construct.py --replication --task_name $task_name --repo_path $repo_path --replication_path $replication_path 
    fi

    if $student; then
        python evaluation_prompt_construct.py --student --task_name $task_name --repo_path $repo_path --exam_path $exam_path --documentation_path $documentation_path
    fi


    if $human; then
        python evaluation_prompt_construct.py --human --task_name $task_name --repo_path $repo_path

    fi

    if ! $replication && ! $student && ! $human; then
        python evaluation_prompt_construct.py --task_name $task_name --repo_path $repo_path --system_prompt_path $system_prompt_path
    fi

done