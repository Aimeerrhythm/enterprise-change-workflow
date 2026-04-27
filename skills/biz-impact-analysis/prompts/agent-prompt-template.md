# Agent Prompt Template

When dispatching the biz-impact-analysis agent, use the following prompt structure:

```
Please analyze the business impact of the following code changes.

## Diff Range

{diff_range}

## Changed File Summary (Coordinator Preprocessed Results)

{git_diff_stat_output}

## Domain Identification Results

{file_to_domain_mapping}

## Instructions

Execute your 5-step analysis process.
Note: Full diff content has been preprocessed by Coordinator, providing file list and domain identification.
In Step 1, only execute `git diff {diff_range} -- {file_path}` for files that need method signature change inspection.
In Step 3 incremental scan, only read specific change content for files matching scan_patterns.
Do not execute `git diff {diff_range}` for full change content on all files.

Please output the impact analysis report in Chinese.
```

## Argument Parsing Rules

| Input | Diff Command |
|-------|-------------|
| `/biz-impact-analysis` | `git diff master...HEAD` |
| `/biz-impact-analysis HEAD~3` | `git diff HEAD~3...HEAD` |
| `/biz-impact-analysis abc123` | `git diff abc123...HEAD` |
| `/biz-impact-analysis abc123 def456` | `git diff abc123...def456` |
