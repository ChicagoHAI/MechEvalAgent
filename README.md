# The Story is Not the Science: Execution-Grounded Evaluation of Mechanistic Interpretability Research

Reproducibility crises across sciences highlight the limitations of the paper-centric review system in assessing the rigor and reproducibility of research. AI agents that autonomously design and generate large volumes of research outputs exacerbate these challenges. In this work, we address the growing challenges of scalability and rigor by flipping the dynamic and developing AI agents as research evaluators. We propose the first execution-grounded evaluation framework that verifies research beyond narrative review by examining code and data alongside the paper. We use mechanistic interpretability research as a testbed, build standardized research output, and develop **MechEvalAgent**, an automated evaluation framework that assesses the *coherence* of the experimental process, the *reproducibility* of results, and the *generalizability* of findings. We show that our framework achieves above 80% agreement with human judges, identifies substantial methodological problems, and surfaces 51 additional issues that human reviewers miss. Our work demonstrates the potential of AI agents to transform research evaluation and pave the way for rigorous scientific practices.

<img width="1435" height="656" alt="Screenshot 2026-02-02 at 19 00 40" src="https://github.com/user-attachments/assets/c899e913-b446-4867-b093-61cb3dfd24b9" />

## Setup

**Requirements:**
- [Scribe](https://github.com/goodfire-ai/scribe) - External package for agent orchestration
- Claude Code CLI configured and authenticated
- Python 3.8+
- Additional packages depend on the project being evaluated

**Dangerous Mode:**
Both `run_critic.sh` and `run_experiment.sh` use the `--dangerously-skip-permissions` flag by default. You can modify this in the respective shell scripts if needed.

## Project Structure

```
eval_agent/
├── run_experiment.sh          # Generate research outputs
├── run_critic.sh              # Run evaluation agents
├── experiment_run.sh          # Batch runner for multiple experiments
├── eval_agent.sh              # Batch runner for evaluations
├── template.sh                # Construct evaluation prompts from templates
├── generate_plan.py           # Generate plan.md from PDF papers
├── evaluation_prompt_construct.py  # Fill prompt templates with paths
└── prompts/
    ├── research_agent_input/  # Input prompts for research agents
    ├── template_open_replication/  # Templates for agent-generated repos
    ├── template_human/        # Templates for human-written repos
    ├── template_doc_only/     # Templates for doc-only ablation
    └── template_no_exe/       # Templates for no-execution ablation
```

## Pipeline Overview

### Stage 1: Generate Research

Generate research outputs by running agent-driven experiments. The example input prompts are in `prompts/research_agent_input`

**Script:** `run_experiment.sh`

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `--prompts` | Comma-separated list of prompt files | `prompts/research_agent_input/circuit_prompt_ioi.txt` |
| `--providers` | Comma-separated providers (claude, gemini, codex) | `claude` |
| `--concurrent` | Max concurrent sessions per provider | `3` |
| `--task-name` | Name of the task | `experiment` |
| `--push` | Create git branch and push results | `false` |

**Example Usage:**
```bash
# Run with default settings
bash run_experiment.sh

# Run with custom prompt
bash run_experiment.sh --task-name counting --prompts prompts/research_agent_input/open_counting.txt

# Run with multiple providers
bash run_experiment.sh --providers claude,gemini --concurrent 2

# Batch run multiple experiments
bash experiment_run.sh
```

**Output Structure:**
```
YOUR_PATH/open_question/{task_name}_{provider}_{timestamp}/
├── logs/           # Agent execution logs
├── notebooks/      # Generated Jupyter notebooks
└── results/        # JSON results and figures
```

### Stage 2: Prepare Evaluation Prompts

Before evaluation, construct the evaluation prompts by filling in template placeholders.

**Script:** `template.sh` (calls `evaluation_prompt_construct.py`)

**Arguments for `evaluation_prompt_construct.py`:**

| Argument | Description | Default |
|----------|-------------|---------|
| `--task_name` | Name of the task | `ioi_l2` |
| `--repo_path` | Path to the repository to evaluate | Required |
| `--system_prompt_path` | Path to original system prompt | For instruction following |
| `--replication_path` | Path to replication outputs | For replicator evaluator |
| `--replication` | Flag to generate replicator_evaluator prompt only | `false` |
| `--student` | Flag to generate student exam prompt | `false` |
| `--human` | Flag for human-written repos (no instruction following) | `false` |
| `--template_dir` | Template directory to use | `templates_open_replication` |
| `--output_dir` | Output directory for filled prompts | `prompts/evaluation/open_question` |

**Example Usage:**
```bash
# For agent-generated repos
python evaluation_prompt_construct.py \
    --task_name counting \
    --repo_path /path/to/counting_claude_2026-01-04/  \
    --system_prompt_path prompts/research_agent_input/open_counting.txt

# For human-written repos
python evaluation_prompt_construct.py \
    --human \
    --task_name my_paper_eval \
    --repo_path /path/to/human_repo/

# Generate replicator evaluator prompt (after replication run)
python evaluation_prompt_construct.py \
    --replication \
    --task_name counting \
    --repo_path /path/to/repo/ \
    --replication_path /path/to/repo/evaluation/replications/
```

### Stage 3: Generate Plan for Human Repos (Optional)

For human-written repos that lack a structured plan, we can generate one from the PDF paper. You can choose to write your own.

**Script:** `generate_plan.py`

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `--file_path` | Path to input PDF | Required |
| `--out_dir` | Output directory for plan files | Required |
| `--claude_cmd` | Claude CLI command with optional flags | `claude` |
| `--timeout_s` | Timeout in seconds for Claude CLI | `1800` |
| `--max_words` | Target max words for concise sections | `400` |

**Example Usage:**
```bash
python generate_plan.py \
    --file_path data/paper.pdf \
    --out_dir experiments_human_repo/paper_eval/
```

**Output:**
- `plan.md` - Concise plan with Objective/Hypothesis/Methodology/Experiments
- `plan_with_evidence.md` - Full plan with evidence quotes and unknowns

### Stage 4: Run Evaluation

Execute the evaluation agents on the research outputs.

**Script:** `run_critic.sh`

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `--prompts` | Comma-separated list of evaluation prompt files | See defaults in script |
| `--providers` | Comma-separated providers | `claude` |
| `--concurrent` | Max concurrent sessions | `3` |
| `--tasks` | Task name identifier | `function_vector` |
| `--repo_path` | Path to repository being evaluated | Required |
| `--push` | Create git branch and push results | `false` |

**Example Usage:**
```bash
# Run single evaluation
bash run_critic.sh \
    --prompts prompts/evaluation/open_question/counting/code_evaluation.txt \
    --repo_path /path/to/counting_repo/ \
    --tasks counting

# Run full evaluation suite
bash run_critic.sh \
    --prompts "prompts/eval/code_evaluation.txt,prompts/eval/consistency_evaluation.txt,prompts/eval/generalization_test.txt,prompts/eval/replicator_model.txt" \
    --repo_path /path/to/repo/ \
    --tasks my_task
```

### Evaluation Order

The evaluation must be run in a specific order due to dependencies:

**For Agent-Generated and Replication Tasks:**
1. First run (can be parallel):
   - `code_evaluation.txt`
   - `consistency_evaluation.txt`
   - `instruction_following.txt`
   - `replicator_model.txt`
   - `generalization_test.txt`

2. Second run (depends on replication results):
   - `replicator_evaluator.txt`

**For Human-Written Repos:**
1. First run (can be parallel):
   - `code_evaluation.txt`
   - `consistency_evaluation.txt`
   - `replicator_model.txt`
   - `generalization_test.txt`

2. Second run (depends on replication results):
   - `replicator_evaluator.txt`

**Batch Evaluation:**
Use `eval_agent.sh` to run the full evaluation pipeline:
```bash
# Edit TASK_NAMES array in eval_agent.sh, then:
bash eval_agent.sh
```

## Evaluation Templates

| Template Directory | Use Case | Notes |
|-------------------|----------|-------|
| `template_open_replication` | Agent-generated repos | Standard evaluation suite |
| `template_human` | Human-written repos | Extra instructions for handling packages, APIs, model loading |
| `template_doc_only` | Ablation study | Documentation-only evaluation |
| `template_no_exe` | Ablation study | No code execution |

**Note for Human Repos:** We recommend update `template_human/code_evaluation.txt` and `template_human/replicator_model.txt` with:
- Path to local model weights
- API keys location or environment setup instructions

## Quick Start Example

```bash
# 1. Generate research on a topic
bash run_experiment.sh \
    --task-name my_experiment \
    --prompts prompts/research_agent_input/my_prompt.txt

# 2. Construct evaluation prompts
python evaluation_prompt_construct.py \
    --task_name my_experiment \
    --repo_path /path/to/output/my_experiment_claude_timestamp/ \
    --system_prompt_path prompts/research_agent_input/my_prompt.txt

# 3. Run evaluation (first batch)
bash run_critic.sh \
    --prompts "prompts/evaluation/open_question/my_experiment/code_evaluation.txt,prompts/evaluation/open_question/my_experiment/consistency_evaluation.txt,prompts/evaluation/open_question/my_experiment/generalization_test.txt,prompts/evaluation/open_question/my_experiment/replicator_model.txt,prompts/evaluation/open_question/my_experiment/instruction_following.txt" \
    --repo_path /path/to/output/my_experiment_claude_timestamp/ \
    --tasks my_experiment

# 4. Run replicator evaluator (after replication completes)
python evaluation_prompt_construct.py \
    --replication \
    --task_name my_experiment \
    --repo_path /path/to/output/my_experiment_claude_timestamp/ \
    --replication_path /path/to/output/my_experiment_claude_timestamp/evaluation/replications/

bash run_critic.sh \
    --prompts prompts/evaluation/open_question/my_experiment/replicator_evaluator.txt \
    --repo_path /path/to/output/my_experiment_claude_timestamp/ \
    --tasks my_experiment
```

## Contributing

We welcome contributions to improve MechEvalAgent. Here's how you can help:

**Reporting Issues**
- Open an issue describing the bug or feature request
- Include steps to reproduce for bugs
- Provide relevant logs or error messages

**Submitting Changes**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Test your changes with the evaluation pipeline
5. Commit with clear messages (`git commit -m "Add: description of change"`)
6. Push to your fork and open a Pull Request

**Areas for Contribution**
- New evaluation templates for different research domains
- Additional provider support (beyond Claude, Gemini, Codex)
- Improved prompt templates for better evaluation accuracy
- Documentation improvements and examples
- Bug fixes and performance optimizations

**Code Style**
- Shell scripts: Follow existing formatting conventions
- Python: Use type hints and docstrings for new functions
- Keep prompts clear and well-structured
