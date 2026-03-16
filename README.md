# QXueYou Daily Quiz Skill

`qxueyou-daily-quiz` 是一个基于 Q学友题库导出数据的练题 Skill。

它支持：

- 每日默认 `100` 题出题
- 单选题 / 多选题 / 判断题混合出题
- 尽量不重复出题，直到题库全部出完
- 用户答题后判题并展示答案与解析
- 统计错误题型
- 写入错题本
- 从错题本继续出题
- 错题连续答对 `3` 次后自动移除

## 目录结构

```text
qxueyou-daily-quiz/
├── README.md
├── SKILL.md
├── reference.md
├── data/
│   └── qxueyou_questions.jsonl
├── scripts/
    └── quiz_manager.py
```

说明：

- `data/qxueyou_questions.jsonl`
  题库数据源
- `scripts/quiz_manager.py`
  出题、判题、错题本管理脚本
- `state/daily_quiz/`
  运行时状态目录，保存 session、answers、grades、错题本等数据

## 前置要求

- Python 3.9+
- 已导出的题库文件：
  - `data/qxueyou_questions.jsonl`

如果题库文件还没生成，需要先在源码仓库中执行导出流程。

## 常用命令

以下命令默认在 `qxueyou-daily-quiz/` 目录下执行。

### 1. 查看当前题库状态

```bash
python scripts/quiz_manager.py status
```

### 2. 正常出题

默认 100 题：

```bash
python scripts/quiz_manager.py start --count 100
```

### 3. 从错题本出题

```bash
python scripts/quiz_manager.py start --source wrong-book --count 100
```

### 4. 判题

```bash
python scripts/quiz_manager.py grade --session-file <session-file> --answers-file <answers-file>
```

### 5. 重置题库进度与错题本状态

```bash
python scripts/quiz_manager.py reset
```

## 出题输出格式

推荐以以下格式向用户展示题目：

```markdown
## 今日题目

本次共 100 题。请按 `题号:答案` 的格式作答，例如：`1:A 2:AC 3:B`。

### 1. [单选题] 题目内容
A. 选项一
B. 选项二
C. 选项三
D. 选项四
```

## 答案文件格式

推荐保存为：

- `state/daily_quiz/answers/<session-id>.json`

格式如下：

```json
{
  "answers": [
    {"index": 1, "answer": "A"},
    {"index": 2, "answer": "BCD"},
    {"index": 3, "answer": "B"}
  ]
}
```

说明：

- `单选题` / `判断题` 使用单个选项，如 `A`
- `多选题` 可写 `ABC`、`A,C`、`A C`

## 错题本规则

- 题目答错时，加入错题本并输出提示
- 已在错题本中的题，再次答错时会保留并更新状态
- 错题连续答对 `3` 次后，从错题本移除并输出提示

相关文件：

- 错题历史：
  - `state/daily_quiz/wrong_questions.jsonl`
- 错题本当前活动状态：
  - `state/daily_quiz/wrong_book_state.json`

## Skill 文件

如果要让其它智能体自动使用这个 Skill，请重点查看：

- `SKILL.md`
- `reference.md`

其中：

- `SKILL.md`
  面向智能体的主流程说明
- `reference.md`
  详细命令、数据结构和输出示例
