#!/usr/bin/env python3
"""Manage daily quiz batches from the exported QXueYou question bank."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = SKILL_DIR.parents[1]
DEFAULT_BANK_PATH = SKILL_DIR / "data/qxueyou_questions.jsonl"
DEFAULT_STATE_DIR = SKILL_DIR / "state/daily_quiz"
DEFAULT_BATCH_SIZE = 100
WRONG_BOOK_REMOVE_CORRECT_STREAK = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create quiz batches, grade answers, and track wrong questions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Create a new quiz batch.")
    start_parser.add_argument(
        "--bank",
        default=str(DEFAULT_BANK_PATH),
        help="Question bank JSONL path.",
    )
    start_parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="Directory used to store quiz state files.",
    )
    start_parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Question count for this batch. Default: 100.",
    )
    start_parser.add_argument(
        "--source",
        choices=("normal", "wrong-book"),
        default="normal",
        help="Question source: normal bank or active wrong-book pool.",
    )
    start_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible batch ordering.",
    )

    grade_parser = subparsers.add_parser("grade", help="Grade a completed quiz batch.")
    grade_parser.add_argument(
        "--session-file",
        required=True,
        help="Session file created by the start command.",
    )
    grade_parser.add_argument(
        "--answers-file",
        required=True,
        help="JSON file containing the user's answers.",
    )
    grade_parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="Directory used to store quiz state files.",
    )

    status_parser = subparsers.add_parser("status", help="Show current quiz progress.")
    status_parser.add_argument(
        "--bank",
        default=str(DEFAULT_BANK_PATH),
        help="Question bank JSONL path.",
    )
    status_parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="Directory used to store quiz state files.",
    )

    reset_parser = subparsers.add_parser(
        "reset", help="Reset quiz progress and clear used-question history."
    )
    reset_parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="Directory used to store quiz state files.",
    )

    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_state_dirs(state_dir: Path) -> dict[str, Path]:
    sessions_dir = state_dir / "sessions"
    grades_dir = state_dir / "grades"
    answers_dir = state_dir / "answers"
    state_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    grades_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)
    return {
        "sessions": sessions_dir,
        "grades": grades_dir,
        "answers": answers_dir,
        "progress": state_dir / "progress.json",
        "wrong_book_history": state_dir / "wrong_questions.jsonl",
        "wrong_book_active": state_dir / "wrong_book_state.json",
    }


def load_bank(bank_path: Path) -> list[dict[str, Any]]:
    if not bank_path.exists():
        raise FileNotFoundError(
            f"Question bank not found: {bank_path}. "
            "Run ./run_export.sh first to export the QXueYou questions."
        )

    records: list[dict[str, Any]] = []
    with bank_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                records.append(item)

    if not records:
        raise RuntimeError(f"Question bank is empty: {bank_path}")

    return records


def load_progress(progress_path: Path) -> dict[str, Any]:
    if not progress_path.exists():
        return {
            "last_session_number": 0,
            "used_serials": [],
            "sessions": {},
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

    return json.loads(progress_path.read_text(encoding="utf-8"))


def save_progress(progress_path: Path, progress: dict[str, Any]) -> None:
    progress["updated_at"] = now_iso()
    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_wrong_book_active(active_path: Path) -> dict[str, dict[str, Any]]:
    if not active_path.exists():
        return {}
    payload = json.loads(active_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {
        str(serial): item
        for serial, item in payload.items()
        if isinstance(item, dict)
    }


def save_wrong_book_active(
    active_path: Path,
    wrong_book_active: dict[str, dict[str, Any]],
) -> None:
    active_path.write_text(
        json.dumps(wrong_book_active, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_answer(answer: str, question_type: str) -> str:
    raw = "".join(ch for ch in answer.upper() if ch.isalnum())
    if question_type == "多选题":
        seen: list[str] = []
        for char in raw:
            if char not in seen:
                seen.append(char)
        return "".join(sorted(seen))
    return raw[:1]


def choose_mixed_questions(
    candidates: list[dict[str, Any]],
    count: int,
    seed: int | None,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[str(item.get("question_type", "")).strip()].append(item)

    for bucket in grouped.values():
        rng.shuffle(bucket)

    ordered_types = sorted(grouped.keys())
    selected: list[dict[str, Any]] = []
    while len(selected) < count:
        added_this_round = False
        ordered_types.sort(key=lambda name: len(grouped[name]), reverse=True)
        for question_type in ordered_types:
            bucket = grouped[question_type]
            if not bucket:
                continue
            selected.append(bucket.pop())
            added_this_round = True
            if len(selected) >= count:
                break
        if not added_this_round:
            break
    return selected


def build_session_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_questions: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        normalized_questions.append(
            {
                "index": index,
                "serial": str(question.get("serial", "")).strip(),
                "question_type": str(question.get("question_type", "")).strip(),
                "question": str(question.get("question", "")).strip(),
                "options": question.get("options", []),
                "answer": str(question.get("answer", "")).strip(),
                "analysis": str(question.get("analysis", "")).strip(),
            }
        )
    return normalized_questions


def create_session(args: argparse.Namespace) -> int:
    bank_path = Path(args.bank)
    state_dir = Path(args.state_dir)
    paths = ensure_state_dirs(state_dir)
    bank = load_bank(bank_path)
    progress = load_progress(paths["progress"])
    wrong_book_active = load_wrong_book_active(paths["wrong_book_active"])
    requested_count = max(1, args.count)

    if args.source == "wrong-book":
        candidates = list(wrong_book_active.values())
        if not candidates:
            print("STATUS: exhausted")
            print("MESSAGE: 当前错题本没有可出题目。")
            print(f"WRONG_BOOK_ACTIVE_FILE: {paths['wrong_book_active']}")
            return 0
        selected_questions = choose_mixed_questions(
            candidates=candidates,
            count=min(requested_count, len(candidates)),
            seed=args.seed,
        )
        remaining_after_pick = len(candidates) - len(selected_questions)
        exhausted_after_pick = remaining_after_pick == 0
    else:
        used_serials = {str(serial) for serial in progress.get("used_serials", [])}
        unseen_questions = [
            item
            for item in bank
            if str(item.get("serial", "")).strip() not in used_serials
        ]
        if not unseen_questions:
            print("STATUS: exhausted")
            print("MESSAGE: 题库中的题目已经全部出完。如需重新开始，请执行 reset。")
            print(f"BANK_PATH: {bank_path}")
            return 0
        selected_questions = choose_mixed_questions(
            candidates=unseen_questions,
            count=min(requested_count, len(unseen_questions)),
            seed=args.seed,
        )
        remaining_after_pick = len(unseen_questions) - len(selected_questions)
        exhausted_after_pick = remaining_after_pick == 0

    progress["last_session_number"] = int(progress.get("last_session_number", 0)) + 1
    session_id = f"session-{progress['last_session_number']:04d}"
    session_file = paths["sessions"] / f"{session_id}.json"
    questions_for_session = build_session_questions(selected_questions)

    session_payload = {
        "session_id": session_id,
        "created_at": now_iso(),
        "status": "pending",
        "source": args.source,
        "requested_count": requested_count,
        "actual_count": len(questions_for_session),
        "remaining_after_pick": remaining_after_pick,
        "all_exhausted_after_pick": exhausted_after_pick,
        "bank_path": str(bank_path),
        "questions": questions_for_session,
    }
    session_file.write_text(
        json.dumps(session_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.source == "normal":
        progress["used_serials"] = progress.get("used_serials", []) + [
            question["serial"] for question in questions_for_session
        ]

    progress.setdefault("sessions", {})[session_id] = {
        "status": "pending",
        "source": args.source,
        "session_file": str(session_file),
        "created_at": session_payload["created_at"],
        "question_count": len(questions_for_session),
        "remaining_after_pick": remaining_after_pick,
    }
    save_progress(paths["progress"], progress)

    print("STATUS: ok")
    print(f"SESSION_ID: {session_id}")
    print(f"SESSION_SOURCE: {args.source}")
    print(f"SESSION_FILE: {session_file}")
    print(f"QUESTION_COUNT: {len(questions_for_session)}")
    print(f"REMAINING_AFTER_PICK: {remaining_after_pick}")
    print(f"POOL_EXHAUSTED_AFTER_PICK: {str(exhausted_after_pick).lower()}")
    if exhausted_after_pick:
        if args.source == "wrong-book":
            print("MESSAGE: 本批次已经取完当前错题本中的全部题目。")
        else:
            print("MESSAGE: 本批次已经取完剩余全部题目。题库已出完，如需重新开始请执行 reset。")
    return 0


def parse_answers_payload(raw_payload: Any) -> dict[int, str]:
    if isinstance(raw_payload, dict):
        if "answers" in raw_payload:
            return parse_answers_payload(raw_payload["answers"])
        answers: dict[int, str] = {}
        for key, value in raw_payload.items():
            if str(key).isdigit():
                answers[int(key)] = str(value).strip()
        return answers

    if isinstance(raw_payload, list):
        answers = {}
        for item in raw_payload:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            answer = item.get("answer")
            if str(index).isdigit() and answer is not None:
                answers[int(index)] = str(answer).strip()
        return answers

    raise ValueError("Unsupported answers file structure.")


def upsert_wrong_book_entry(
    wrong_book_active: dict[str, dict[str, Any]],
    detail: dict[str, Any],
    session_id: str,
) -> tuple[bool, dict[str, Any]]:
    serial = str(detail["serial"])
    entry = wrong_book_active.get(serial)
    was_new = entry is None
    if was_new:
        entry = {
            "serial": serial,
            "question_type": detail["question_type"],
            "question": detail["question"],
            "options": detail["options"],
            "answer": detail["correct_answer"],
            "analysis": detail["analysis"],
            "added_at": now_iso(),
            "correct_streak": 0,
            "wrong_count": 0,
        }

    entry.update(
        {
            "question_type": detail["question_type"],
            "question": detail["question"],
            "options": detail["options"],
            "answer": detail["correct_answer"],
            "analysis": detail["analysis"],
            "last_user_answer": detail["user_answer"],
            "last_session_id": session_id,
            "last_wrong_at": now_iso(),
            "updated_at": now_iso(),
            "correct_streak": 0,
            "wrong_count": int(entry.get("wrong_count", 0)) + 1,
        }
    )
    wrong_book_active[serial] = entry
    return was_new, entry


def register_correct_on_wrong_book(
    wrong_book_active: dict[str, dict[str, Any]],
    detail: dict[str, Any],
    session_id: str,
) -> tuple[bool, dict[str, Any] | None]:
    serial = str(detail["serial"])
    entry = wrong_book_active.get(serial)
    if entry is None:
        return False, None

    entry["correct_streak"] = int(entry.get("correct_streak", 0)) + 1
    entry["last_user_answer"] = detail["user_answer"]
    entry["last_session_id"] = session_id
    entry["last_correct_at"] = now_iso()
    entry["updated_at"] = now_iso()
    if int(entry["correct_streak"]) >= WRONG_BOOK_REMOVE_CORRECT_STREAK:
        removed_entry = dict(entry)
        wrong_book_active.pop(serial, None)
        return True, removed_entry
    return False, entry


def grade_session(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    paths = ensure_state_dirs(state_dir)
    session_file = Path(args.session_file)
    answers_file = Path(args.answers_file)

    if not session_file.exists():
        raise FileNotFoundError(f"Session file not found: {session_file}")
    if not answers_file.exists():
        raise FileNotFoundError(f"Answers file not found: {answers_file}")

    session_payload = json.loads(session_file.read_text(encoding="utf-8"))
    answers_payload = json.loads(answers_file.read_text(encoding="utf-8"))
    user_answers = parse_answers_payload(answers_payload)
    questions = session_payload.get("questions", [])
    wrong_book_active = load_wrong_book_active(paths["wrong_book_active"])

    details: list[dict[str, Any]] = []
    wrong_by_type: Counter[str] = Counter()
    correct_count = 0
    answered_count = 0
    added_to_wrong_book: list[dict[str, Any]] = []
    removed_from_wrong_book: list[dict[str, Any]] = []

    for question in questions:
        index = int(question["index"])
        question_type = str(question["question_type"])
        correct_answer = str(question["answer"])
        user_answer = user_answers.get(index, "")
        normalized_user = normalize_answer(user_answer, question_type)
        normalized_correct = normalize_answer(correct_answer, question_type)
        is_answered = bool(normalized_user)
        is_correct = is_answered and normalized_user == normalized_correct

        if is_answered:
            answered_count += 1
        if is_correct:
            correct_count += 1
        else:
            wrong_by_type[question_type] += 1

        detail = {
            "index": index,
            "serial": question["serial"],
            "question_type": question_type,
            "question": question["question"],
            "options": question["options"],
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "analysis": question["analysis"],
        }
        details.append(detail)

        if is_correct:
            should_remove, wrong_book_entry = register_correct_on_wrong_book(
                wrong_book_active=wrong_book_active,
                detail=detail,
                session_id=session_payload["session_id"],
            )
            if should_remove and wrong_book_entry is not None:
                removed_from_wrong_book.append(
                    {
                        "serial": wrong_book_entry["serial"],
                        "question_type": wrong_book_entry["question_type"],
                        "question": wrong_book_entry["question"],
                        "correct_streak": WRONG_BOOK_REMOVE_CORRECT_STREAK,
                    }
                )
        else:
            was_new, wrong_book_entry = upsert_wrong_book_entry(
                wrong_book_active=wrong_book_active,
                detail=detail,
                session_id=session_payload["session_id"],
            )
            if was_new:
                added_to_wrong_book.append(
                    {
                        "serial": wrong_book_entry["serial"],
                        "question_type": wrong_book_entry["question_type"],
                        "question": wrong_book_entry["question"],
                    }
                )

    total = len(questions)
    wrong_count = total - correct_count
    accuracy = round((correct_count / total) * 100, 2) if total else 0.0
    grade_file = paths["grades"] / f"{session_payload['session_id']}.json"
    grade_payload = {
        "session_id": session_payload["session_id"],
        "source": session_payload.get("source", "normal"),
        "graded_at": now_iso(),
        "total": total,
        "answered": answered_count,
        "correct": correct_count,
        "wrong": wrong_count,
        "accuracy": accuracy,
        "wrong_by_type": dict(wrong_by_type),
        "added_to_wrong_book": added_to_wrong_book,
        "removed_from_wrong_book": removed_from_wrong_book,
        "details": details,
        "session_exhausted_pool": bool(session_payload.get("all_exhausted_after_pick")),
    }
    grade_file.write_text(
        json.dumps(grade_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with paths["wrong_book_history"].open("a", encoding="utf-8") as file:
        for detail in details:
            if detail["is_correct"]:
                continue
            wrong_record = {
                "session_id": session_payload["session_id"],
                "recorded_at": now_iso(),
                "serial": detail["serial"],
                "question_type": detail["question_type"],
                "question": detail["question"],
                "options": detail["options"],
                "user_answer": detail["user_answer"],
                "correct_answer": detail["correct_answer"],
                "analysis": detail["analysis"],
            }
            file.write(json.dumps(wrong_record, ensure_ascii=False) + "\n")

    save_wrong_book_active(paths["wrong_book_active"], wrong_book_active)

    session_payload["status"] = "graded"
    session_payload["graded_at"] = now_iso()
    session_payload["answers_file"] = str(answers_file)
    session_payload["grade_file"] = str(grade_file)
    session_file.write_text(
        json.dumps(session_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    progress = load_progress(paths["progress"])
    progress.setdefault("sessions", {}).setdefault(session_payload["session_id"], {})
    progress["sessions"][session_payload["session_id"]].update(
        {
            "status": "graded",
            "source": session_payload.get("source", "normal"),
            "answers_file": str(answers_file),
            "grade_file": str(grade_file),
            "graded_at": session_payload["graded_at"],
            "accuracy": accuracy,
        }
    )
    save_progress(paths["progress"], progress)

    print("STATUS: graded")
    print(f"GRADE_FILE: {grade_file}")
    print(f"TOTAL: {total}")
    print(f"ANSWERED: {answered_count}")
    print(f"CORRECT: {correct_count}")
    print(f"WRONG: {wrong_count}")
    print(f"ACCURACY: {accuracy}")
    print(f"WRONG_BY_TYPE: {json.dumps(dict(wrong_by_type), ensure_ascii=False)}")
    print(f"WRONG_BOOK_FILE: {paths['wrong_book_history']}")
    print(f"WRONG_BOOK_ACTIVE_FILE: {paths['wrong_book_active']}")
    print(f"WRONG_BOOK_ACTIVE_TOTAL: {len(wrong_book_active)}")
    print(f"ADDED_TO_WRONG_BOOK_COUNT: {len(added_to_wrong_book)}")
    print(f"REMOVED_FROM_WRONG_BOOK_COUNT: {len(removed_from_wrong_book)}")
    if added_to_wrong_book:
        print(
            "MESSAGE: 以下题目已加入错题本："
            + json.dumps(added_to_wrong_book, ensure_ascii=False)
        )
    if removed_from_wrong_book:
        print(
            "MESSAGE: 以下题目已连续答对3次，已从错题本移除："
            + json.dumps(removed_from_wrong_book, ensure_ascii=False)
        )
    if session_payload.get("all_exhausted_after_pick"):
        if session_payload.get("source") == "wrong-book":
            print("MESSAGE: 本批次已覆盖错题本当前最后一批题目。")
        else:
            print("MESSAGE: 本批次已覆盖题库最后一批题目。如需重新开始，请执行 reset。")
    return 0


def show_status(args: argparse.Namespace) -> int:
    bank_path = Path(args.bank)
    state_dir = Path(args.state_dir)
    paths = ensure_state_dirs(state_dir)
    bank = load_bank(bank_path)
    progress = load_progress(paths["progress"])
    wrong_book_active = load_wrong_book_active(paths["wrong_book_active"])
    used_serials = {str(serial) for serial in progress.get("used_serials", [])}
    remaining = max(len(bank) - len(used_serials), 0)

    print("STATUS: ready")
    print(f"BANK_TOTAL: {len(bank)}")
    print(f"USED_TOTAL: {len(used_serials)}")
    print(f"REMAINING_TOTAL: {remaining}")
    print(f"WRONG_BOOK_ACTIVE_TOTAL: {len(wrong_book_active)}")
    print(f"STATE_DIR: {state_dir}")
    print(f"WRONG_BOOK_FILE: {paths['wrong_book_history']}")
    print(f"WRONG_BOOK_ACTIVE_FILE: {paths['wrong_book_active']}")
    return 0


def reset_progress(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    if state_dir.exists():
        archive_dir = state_dir.with_name(
            f"{state_dir.name}_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.move(str(state_dir), str(archive_dir))
        print(f"ARCHIVE_DIR: {archive_dir}")

    paths = ensure_state_dirs(state_dir)
    save_progress(
        paths["progress"],
        {
            "last_session_number": 0,
            "used_serials": [],
            "sessions": {},
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
    )
    save_wrong_book_active(paths["wrong_book_active"], {})
    print("STATUS: reset")
    print(f"STATE_DIR: {state_dir}")
    print("MESSAGE: 题库进度与错题本状态已重置，可以重新开始新一轮出题。")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "start":
        return create_session(args)
    if args.command == "grade":
        return grade_session(args)
    if args.command == "status":
        return show_status(args)
    if args.command == "reset":
        return reset_progress(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
