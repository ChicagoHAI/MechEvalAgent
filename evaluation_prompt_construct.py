import sys
import os
import argparse
from pathlib import Path

def fill_evaluation_prompts(repo_path, task_name, template_dir, output_dir, system_prompt_path=None, replication_path=None, replication=False, student=False, exam_path=None, documentation_path=None):
    """
    Fill in REPO_PATH, SYSTEM_PROMPT_PATH, and REPLICATION_PATH in evaluation prompt files.

    Args:
        repo_path: Path to the repository
        system_prompt_path: Path to system prompt (for instruction_following.txt)
        replication_path: Path to replication output (for replicator_evaluator.txt)
    """
    prompts_dir =  "prompts/{template_dir}"
    output_dir = f"prompts/{output_dir}"
    os.makedirs(output_dir, exist_ok=True)

    evaluation_prompts = [
        "consistency_evaluation.txt",
        "code_evaluation.txt",
        "generalization_test.txt",
        "instruction_following.txt",
        "replicator_model.txt"
    ]

    if replication:
        evaluation_prompts = ["replicator_evaluator.txt"]
    
    if student:
        
        evaluation_prompts = ["student.txt"]

    if system_prompt_path == None:
        if "instruction_following.txt" in evaluation_prompts:
            evaluation_prompts.remove("instruction_following.txt")

    print(f"Filling prompts with REPO_PATH: {repo_path}\n")

    for prompt_file in evaluation_prompts:
        template_path = f"{prompts_dir}/{prompt_file}"
        if not os.path.exists(template_path):
            continue

        text = open(template_path, "r").read()
        print(prompt_file)

        # Build replacements based on the specific file
        replacements = {"REPO_PATH": repo_path}

        if prompt_file == "instruction_following.txt" or prompt_file == "instruction_following_l3.txt":
            replacements["SYSTEM_PROMPT"] = system_prompt_path or ""

        if prompt_file == "replicator_evaluator.txt":
            replacements["REPLICATION_PATH"] = replication_path or ""

        if prompt_file == "student.txt":
            replacements["EXAM_PATH"] = exam_path or ""
            replacements["DOCUMENTATION_PATH"] = documentation_path or ""
        
        filled = text.format(**replacements)

        
        output_path = f"{output_dir}/{prompt_file}"
        with open(output_path, "w") as f:
            f.write(filled)
        print(f"✅ {prompt_file}")

    print(f"\nDone! Saved to: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--replication",action="store_true")
    parser.add_argument("--task_name", type=str, default="ioi_l2")
    parser.add_argument("--repo_path", type=str, default="YOUR REPO")
    parser.add_argument("--system_prompt_path", type=str, default="YOUR SYSTEM PROMPT")
    parser.add_argument("--replication_path", type=str, default="YOUR REPLICATION PATH")

    parser.add_argument("--student", action="store_true")
    parser.add_argument("--exam_path", type=str, default="YOUR EXAM PATH")
    parser.add_argument("--documentation_path", type=str, default="YOUR DOCUMENTATION PATH")

    parser.add_argument("--human", action="store_true")
    parser.add_argument("--template_dir", type=str, default="templates_open_replication")
    parser.add_argument("--output_dir", type=str, default="prompts/evaluation/open_question")


    args = parser.parse_args()
    task_name = args.task_name
    repo_path = args.repo_path
    if args.human:
        system_prompt_path = None
    else:
        system_prompt_path = args.system_prompt_path
    
    if args.replication:
        replication = True
        replication_path = args.replication_path
    else:
        replication = False
        replication_path = None
    if args.student:
        student = True
        exam_path = args.exam_path
        documentation_path = args.documentation_path
    else:
        student = False
        exam_path = None
        documentation_path = None

 
    fill_evaluation_prompts(repo_path, task_name, system_prompt_path, replication_path, replication, student, exam_path, documentation_path)
