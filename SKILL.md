---
name: qxueyou-daily-quiz
description: Generate daily quiz batches from `data/qxueyou_questions.jsonl`, avoid repeated questions across sessions, grade user answers, show analyses, summarize wrong question types, and update a wrong-question notebook. Use when the user asks to daily practice questions, draw 100 questions, continue a question bank session, grade answers, review analyses, or manage a wrong-book from the exported QXueYou bank.
---

# QXueYou Daily Quiz

以下路径默认相对 `qxueyou-daily-quiz/` 目录本身。

## Purpose

Use this skill when the user wants an agent to:

- 抽取每日题目，默认 `100` 题
- 尽量不重复出题，直到题库全部出完
- 在用户答完后判题并展示解析
- 输出答题总结
- 统计错误题型
- 写入错题本
- 支持从错题本继续出题
- 连续答对错题本题目 `3` 次后自动移除

## Prerequisite

The exported question bank must exist at:

- `data/qxueyou_questions.jsonl`

If the file does not exist, tell the user to run:

```bash
./run_export.sh
```

## Utility Script

Use this script for batch management:

```bash
python scripts/quiz_manager.py <command>
```

Supported commands:

- `start`: create a new batch
- `grade`: grade a finished batch
- `status`: inspect remaining questions
- `reset`: clear used-question history and restart the pool

## Default Strategy

- Default batch size: `100`
- Default selection strategy: `mixed`
- `mixed` means: interleave question types while still avoiding repeated `serial` values
- Do not repeat questions until the unseen pool is exhausted
- Wrong-book sessions also use `mixed`
- Wrong-book questions remain available until they are answered correctly `3` times
- If all questions have already been used, tell the user that the pool is exhausted and ask whether they want to reset

## Agent Workflow

### 1. Start a new batch

Run:

```bash
python scripts/quiz_manager.py start --count 100
```

If the user explicitly wants to practice from the wrong book, run:

```bash
python scripts/quiz_manager.py start --source wrong-book --count 100
```

Then read the generated `SESSION_FILE`.

Important:

- Never reveal `answer` or `analysis` before the user submits answers
- Present questions in the same order as the session file
- If the script says `POOL_EXHAUSTED_AFTER_PICK: true`, tell the user this is the final unseen batch
- If `SESSION_SOURCE` is `wrong-book`, tell the user this batch is from the wrong-question notebook

### 2. Present questions

Use this output format:

```markdown
## 今日题目

本次共 {count} 题。请按 `题号:答案` 的格式作答，例如：`1:A 2:AC 3:B`。

### 1. [单选题] 题目内容
A. 选项一
B. 选项二
C. 选项三
D. 选项四

### 2. [多选题] 题目内容
A. 选项一
B. 选项二
C. 选项三
D. 选项四

### 3. [判断题] 题目内容
A. 正确
B. 错误
```

Rules:

- Use the session `index` as the displayed question number
- Keep `question_type` visible
- Keep options in original order
- Do not show the standard answer before grading

### 3. Collect user answers

Create an answers JSON file under:

- `state/daily_quiz/answers/<session-id>.json`

Use this file structure:

```json
{
  "answers": [
    {"index": 1, "answer": "A"},
    {"index": 2, "answer": "ACD"},
    {"index": 3, "answer": "B"}
  ]
}
```

Guidelines:

- `单选题` / `判断题` use a single option such as `A`
- `多选题` may use `ABC`, `A,C`, or `A C`; the script will normalize it
- Missing answers are allowed, but they count as wrong in the final summary

### 4. Grade the batch

Run:

```bash
python scripts/quiz_manager.py grade --session-file <session-file> --answers-file <answers-file>
```

Then read the generated `GRADE_FILE`.

The script also appends wrong answers to:

- `state/daily_quiz/wrong_questions.jsonl`

It also maintains the active wrong-book state at:

- `state/daily_quiz/wrong_book_state.json`

### 5. Present grading results

Always include:

- total count
- answered count
- correct count
- wrong count
- accuracy
- wrong question types
- newly added wrong-book questions
- removed wrong-book questions
- full option text when showing answers and analyses
- bold the correct answer option content instead of showing only a letter

Use this response shape:

```markdown
## 答题结果

- 总题数：{total}
- 已作答：{answered}
- 正确：{correct}
- 错误：{wrong}
- 正确率：{accuracy}%

## 错误题型统计

- 单选题：{single_wrong}
- 多选题：{multi_wrong}
- 判断题：{judge_wrong}

## 错题与解析

### 2. [多选题] 题目内容
- A. 选项一
- B. **选项二**
- C. **选项三**
- D. **选项四**
- 你的答案：AC
- 正确答案：**B / 选项二；C / 选项三；D / 选项四**
- 解析：...

### 7. [判断题] 题目内容
- A. **正确**
- B. 错误
- 你的答案：B
- 正确答案：**A / 正确**
- 解析：...

## 错题本提示

- 新加入错题本：{added_count}
- 连续答对3次后移除：{removed_count}
```

If the user got a question correct, you may keep it concise.
Focus detailed analysis on wrong questions unless the user explicitly asks for full per-question review.

When presenting any answer explanation:

- always include the full option list for that question
- never only say `正确答案：B`
- instead, map the answer key back to the actual option text
- bold the correct option content so the user can identify it at a glance
- for multiple-choice questions, bold every correct option

If the grade output includes newly added wrong-book items:

- explicitly tell the user those questions have been added to the wrong book

If the grade output includes removed wrong-book items:

- explicitly tell the user those questions were removed because they were answered correctly `3` times

### 6. Continue or reset

If the user asks for a new batch:

- run `start` again
- do not reset unless the user explicitly wants to restart the full pool
- if the user explicitly wants to review错题本, use `--source wrong-book`

If the pool is exhausted:

- tell the user all questions have been used
- explain that they can run:

```bash
python scripts/quiz_manager.py reset
```

## Important Files

- Skill guide: `SKILL.md`
- Detailed reference: `reference.md`
- Utility script: `scripts/quiz_manager.py`

## Additional Resource

For command outputs, answer file examples, and grade file structure, read:

- [reference.md](reference.md)
