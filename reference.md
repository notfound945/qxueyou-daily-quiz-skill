# Reference

以下路径默认相对 `qxueyou-daily-quiz/` 目录本身。

## Command Examples

### Start a default 100-question batch

```bash
python scripts/quiz_manager.py start --count 100
```

Possible stdout:

```text
STATUS: ok
SESSION_ID: session-0001
SESSION_FILE: state/daily_quiz/sessions/session-0001.json
QUESTION_COUNT: 100
REMAINING_AFTER_PICK: 1066
POOL_EXHAUSTED_AFTER_PICK: false
```

### Start a wrong-book batch

```bash
python scripts/quiz_manager.py start --source wrong-book --count 100
```

### Check remaining questions

```bash
python scripts/quiz_manager.py status
```

### Reset question usage history

```bash
python scripts/quiz_manager.py reset
```

## Session File Shape

`SESSION_FILE` contains the full batch, including answers and analyses for grading:

```json
{
  "session_id": "session-0001",
  "status": "pending",
  "source": "normal",
  "requested_count": 100,
  "actual_count": 100,
  "remaining_after_pick": 1066,
  "all_exhausted_after_pick": false,
  "questions": [
    {
      "index": 1,
      "serial": "21",
      "question_type": "单选题",
      "question": "题目内容",
      "options": [{"key": "A", "text": "选项内容"}],
      "answer": "D",
      "analysis": "解析内容"
    }
  ]
}
```

## Answers File Shape

Recommended file path:

- `state/daily_quiz/answers/<session-id>.json`

Supported formats:

```json
{
  "answers": [
    {"index": 1, "answer": "A"},
    {"index": 2, "answer": "BCD"}
  ]
}
```

or:

```json
{
  "1": "A",
  "2": "BCD"
}
```

## Grade File Shape

The `grade` command writes:

- `state/daily_quiz/grades/<session-id>.json`

Shape:

```json
{
  "session_id": "session-0001",
  "source": "normal",
  "total": 100,
  "answered": 100,
  "correct": 88,
  "wrong": 12,
  "accuracy": 88.0,
  "wrong_by_type": {
    "单选题": 7,
    "多选题": 3,
    "判断题": 2
  },
  "added_to_wrong_book": [
    {
      "serial": "1078",
      "question_type": "判断题",
      "question": "题目内容"
    }
  ],
  "removed_from_wrong_book": [
    {
      "serial": "21",
      "question_type": "单选题",
      "question": "题目内容",
      "correct_streak": 3
    }
  ],
  "details": [
    {
      "index": 1,
      "serial": "21",
      "question_type": "单选题",
      "question": "题目内容",
      "options": [{"key": "A", "text": "选项内容"}],
      "user_answer": "A",
      "correct_answer": "D",
      "is_correct": false,
      "analysis": "解析内容"
    }
  ]
}
```

## Wrong Book

Wrong answers are appended to:

- `state/daily_quiz/wrong_questions.jsonl`

Active wrong-book state is stored at:

- `state/daily_quiz/wrong_book_state.json`

Each line is one wrong-answer record with:

- session id
- recorded time
- serial
- question type
- question
- options
- user answer
- correct answer
- analysis

Each active wrong-book entry tracks at least:

- serial
- question type
- question
- answer
- analysis
- wrong count
- current correct streak

Rule:

- 当题目答错时，加入或保留在错题本中，并输出提示
- 当题目已经在错题本中且连续答对 `3` 次时，从错题本移除，并输出提示

## Recommended Agent Output

### Batch release

```markdown
## 今日题目

本次共 100 题，请按 `题号:答案` 格式提交，例如：`1:A 2:BC 3:B`。
```

### Final summary

```markdown
## 答题总结

- 总题数：100
- 正确：88
- 错误：12
- 正确率：88.0%

## 错误题型统计

- 单选题：7
- 多选题：3
- 判断题：2

## 错题本变更

- 新加入错题本：2
- 从错题本移除：1

## 错题本

已记录到 `state/daily_quiz/wrong_questions.jsonl`
当前错题本活动状态位于 `state/daily_quiz/wrong_book_state.json`
```
