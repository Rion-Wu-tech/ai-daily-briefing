"""SQLite history, feedback and source-health storage for the briefing."""

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


FEEDBACK_WEIGHTS = {
    "opened": 1,
    "saved": 3,
    "drafted": 5,
    "published": 8,
    "dismissed": -6,
}


class BriefingStore:
    """Persist item appearances without coupling storage to source parsing."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS items (
                    item_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '',
                    section TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    selected_count INTEGER NOT NULL DEFAULT 0,
                    last_score INTEGER NOT NULL DEFAULT 0,
                    source_count INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS appearances (
                    run_date TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    section TEXT NOT NULL DEFAULT '',
                    score INTEGER NOT NULL DEFAULT 0,
                    source_count INTEGER NOT NULL DEFAULT 1,
                    selected INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (run_date, item_key),
                    FOREIGN KEY (item_key) REFERENCES items(item_key)
                );

                CREATE INDEX IF NOT EXISTS idx_appearances_item_date
                    ON appearances(item_key, run_date DESC);

                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (item_key) REFERENCES items(item_key)
                );

                CREATE INDEX IF NOT EXISTS idx_feedback_item_date
                    ON feedback(item_key, created_at DESC);

                CREATE TABLE IF NOT EXISTS source_runs (
                    run_date TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    checked_at TEXT NOT NULL,
                    PRIMARY KEY (run_date, source)
                );
                """
            )
            self._ensure_column(connection, "items", "category", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "items", "tags_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(connection, "items", "signals_json", "TEXT NOT NULL DEFAULT '[]'")

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )

    def annotate_items(
        self,
        items: List[Dict[str, Any]],
        run_date: str,
    ) -> None:
        """Attach first-seen and momentum fields before the current run is saved."""
        with self._connect() as connection:
            for rank, item in enumerate(items, 1):
                item_key = str(item.get("item_key", ""))
                if not item_key:
                    continue
                stored = connection.execute(
                    "SELECT * FROM items WHERE item_key = ?",
                    (item_key,),
                ).fetchone()
                previous = connection.execute(
                    """
                    SELECT rank, score, source_count, run_date
                    FROM appearances
                    WHERE item_key = ? AND run_date < ?
                    ORDER BY run_date DESC
                    LIMIT 1
                    """,
                    (item_key, run_date),
                ).fetchone()

                item["current_rank"] = rank
                if stored is None:
                    item.update(
                        {
                            "first_seen": run_date,
                            "last_seen": run_date,
                            "seen_count": 0,
                            "repeat_count": 0,
                            "score_delta": 0,
                            "rank_delta": 0,
                            "history_status": "首次出现",
                        }
                    )
                    continue

                if stored["first_seen"] == run_date and previous is None:
                    item.update(
                        {
                            "first_seen": stored["first_seen"],
                            "last_seen": stored["last_seen"],
                            "seen_count": int(stored["seen_count"]),
                            "repeat_count": 0,
                            "score_delta": 0,
                            "rank_delta": 0,
                            "history_status": "首次出现",
                        }
                    )
                    continue

                seen_count = int(stored["seen_count"])
                score_delta = (
                    int(item.get("overall_score", item.get("rion_score", 0)))
                    - int(previous["score"])
                    if previous is not None
                    else 0
                )
                rank_delta = int(previous["rank"]) - rank if previous is not None else 0
                source_grew = (
                    previous is not None
                    and int(item.get("source_count", 1)) > int(previous["source_count"])
                )
                status = "持续升温" if score_delta >= 5 or rank_delta >= 3 or source_grew else "持续跟踪"
                item.update(
                    {
                        "first_seen": stored["first_seen"],
                        "last_seen": stored["last_seen"],
                        "seen_count": seen_count,
                        "repeat_count": max(0, seen_count),
                        "score_delta": score_delta,
                        "rank_delta": rank_delta,
                        "history_status": status,
                    }
                )

    def record_items(
        self,
        items: List[Dict[str, Any]],
        run_date: str,
        selected_keys: Optional[Iterable[str]] = None,
    ) -> None:
        """Upsert one appearance per item per day; reruns never inflate counts."""
        selected = set(selected_keys or [])
        with self._connect() as connection:
            for rank, item in enumerate(items, 1):
                item_key = str(item.get("item_key", ""))
                if not item_key:
                    continue
                score = int(item.get("overall_score", item.get("rion_score", 0)))
                source_count = int(item.get("source_count", 1))
                is_selected = 1 if item_key in selected else 0
                existing = connection.execute(
                    "SELECT seen_count, selected_count FROM items WHERE item_key = ?",
                    (item_key,),
                ).fetchone()
                appearance = connection.execute(
                    "SELECT 1 FROM appearances WHERE run_date = ? AND item_key = ?",
                    (run_date, item_key),
                ).fetchone()

                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO items (
                            item_key, title, url, section, source, first_seen,
                            last_seen, seen_count, selected_count, last_score,
                            source_count, category, tags_json, signals_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item_key,
                            str(item.get("display_title") or item.get("title") or item.get("name") or ""),
                            str(item.get("url", "")),
                            str(item.get("section", "")),
                            str(item.get("source", "")),
                            run_date,
                            run_date,
                            is_selected,
                            score,
                            source_count,
                            str(item.get("category", "")),
                            json.dumps(item.get("tags", []), ensure_ascii=False),
                            json.dumps(
                                item.get("matched_signals", []),
                                ensure_ascii=False,
                            ),
                        ),
                    )
                else:
                    seen_increment = 0 if appearance else 1
                    selected_increment = 0 if appearance else is_selected
                    connection.execute(
                        """
                        UPDATE items
                        SET title = ?, url = ?, section = ?, source = ?,
                            last_seen = ?, seen_count = seen_count + ?,
                            selected_count = selected_count + ?, last_score = ?,
                            source_count = ?, category = ?, tags_json = ?,
                            signals_json = ?
                        WHERE item_key = ?
                        """,
                        (
                            str(item.get("display_title") or item.get("title") or item.get("name") or ""),
                            str(item.get("url", "")),
                            str(item.get("section", "")),
                            str(item.get("source", "")),
                            run_date,
                            seen_increment,
                            selected_increment,
                            score,
                            source_count,
                            str(item.get("category", "")),
                            json.dumps(item.get("tags", []), ensure_ascii=False),
                            json.dumps(
                                item.get("matched_signals", []),
                                ensure_ascii=False,
                            ),
                            item_key,
                        ),
                    )

                connection.execute(
                    """
                    INSERT INTO appearances (
                        run_date, item_key, rank, section, score, source_count, selected
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_date, item_key) DO UPDATE SET
                        rank = excluded.rank,
                        section = excluded.section,
                        score = excluded.score,
                        source_count = excluded.source_count,
                        selected = excluded.selected
                    """,
                    (
                        run_date,
                        item_key,
                        rank,
                        str(item.get("section", "")),
                        score,
                        source_count,
                        is_selected,
                    ),
                )

    def rank_history(self, item_key: str) -> List[Dict[str, int]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_date, rank, score, source_count
                FROM appearances
                WHERE item_key = ?
                ORDER BY run_date
                """,
                (item_key,),
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_item(self, target: str) -> Dict[str, Any]:
        target = target.strip()
        if not target:
            raise ValueError("反馈目标不能为空")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM items
                WHERE item_key = ? OR url = ? OR title = ?
                ORDER BY last_seen DESC
                LIMIT 1
                """,
                (target, target, target),
            ).fetchone()
            if row is None:
                matches = connection.execute(
                    """
                    SELECT * FROM items
                    WHERE title LIKE ?
                    ORDER BY last_seen DESC
                    LIMIT 2
                    """,
                    (f"%{target}%",),
                ).fetchall()
                if len(matches) == 1:
                    row = matches[0]
                elif len(matches) > 1:
                    raise ValueError("匹配到多条内容，请使用完整标题、链接或 item_key")
        if row is None:
            raise ValueError("历史库中找不到这条内容，请先正常生成一次早报")
        return dict(row)

    def record_feedback(
        self,
        target: str,
        action: str,
        note: str = "",
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        if action not in FEEDBACK_WEIGHTS:
            raise ValueError(f"不支持的反馈动作: {action}")
        item = self.resolve_item(target)
        timestamp = created_at or datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO feedback (item_key, action, note, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (item["item_key"], action, note.strip(), timestamp),
            )
        return {
            "item_key": item["item_key"],
            "title": item["title"],
            "url": item["url"],
            "action": action,
            "weight": FEEDBACK_WEIGHTS[action],
            "note": note.strip(),
            "created_at": timestamp,
        }

    def apply_feedback(self, items: List[Dict[str, Any]]) -> None:
        """Apply bounded item/source/category preference boosts to new rankings."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT f.item_key, f.action, i.source, i.category
                FROM feedback f
                JOIN items i ON i.item_key = f.item_key
                """
            ).fetchall()

        item_scores: Dict[str, int] = {}
        source_scores: Dict[str, List[int]] = {}
        category_scores: Dict[str, List[int]] = {}
        for row in rows:
            weight = FEEDBACK_WEIGHTS.get(row["action"], 0)
            item_scores[row["item_key"]] = item_scores.get(row["item_key"], 0) + weight
            source = str(row["source"] or "")
            category = str(row["category"] or "")
            if source:
                source_scores.setdefault(source, []).append(weight)
            if category:
                category_scores.setdefault(category, []).append(weight)

        source_adjustments = {
            key: max(-5, min(5, round(sum(values) / len(values))))
            for key, values in source_scores.items()
        }
        category_adjustments = {
            key: max(-5, min(5, round(sum(values) / len(values))))
            for key, values in category_scores.items()
        }
        for item in items:
            base_score = int(item.get("overall_score", item.get("rion_score", 0)))
            exact = max(-8, min(8, item_scores.get(str(item.get("item_key", "")), 0)))
            source = source_adjustments.get(str(item.get("source", "")), 0)
            category = category_adjustments.get(str(item.get("category", "")), 0)
            adjustment = max(-12, min(12, exact + source + category))
            item["base_overall_score"] = base_score
            item["feedback_score"] = adjustment
            item["overall_score"] = max(0, min(96, base_score + adjustment))
            item["rion_score"] = item["overall_score"]
            reasons = []
            if exact:
                reasons.append("你对这条内容有过反馈")
            if source:
                reasons.append("该来源符合近期偏好")
            if category:
                reasons.append("该类别符合近期偏好")
            item["feedback_reason"] = "；".join(reasons)

    def record_source_runs(
        self,
        run_date: str,
        results: Iterable[Dict[str, Any]],
    ) -> None:
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            for result in results:
                source = str(result.get("source", "")).strip()
                if not source:
                    continue
                connection.execute(
                    """
                    INSERT INTO source_runs (
                        run_date, source, status, item_count, error,
                        latency_ms, checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_date, source) DO UPDATE SET
                        status = excluded.status,
                        item_count = excluded.item_count,
                        error = excluded.error,
                        latency_ms = excluded.latency_ms,
                        checked_at = excluded.checked_at
                    """,
                    (
                        run_date,
                        source,
                        str(result.get("status", "ok")),
                        int(result.get("item_count", 0)),
                        str(result.get("error", ""))[:500],
                        int(result.get("latency_ms", 0)),
                        checked_at,
                    ),
                )

    def weekly_summary(
        self,
        days: int = 7,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        days = max(1, min(int(days), 31))
        end = date.fromisoformat(end_date) if end_date else date.today()
        start = end - timedelta(days=days - 1)
        start_text = start.isoformat()
        end_text = end.isoformat()
        with self._connect() as connection:
            top_items = connection.execute(
                """
                SELECT i.item_key, i.title, i.url, i.section, i.source,
                       COUNT(*) AS days_seen,
                       ROUND(AVG(a.score), 1) AS avg_score,
                       MIN(a.rank) AS best_rank,
                       SUM(a.selected) AS selected_days
                FROM appearances a
                JOIN items i ON i.item_key = a.item_key
                WHERE a.run_date BETWEEN ? AND ?
                GROUP BY i.item_key
                ORDER BY selected_days DESC, days_seen DESC, avg_score DESC
                LIMIT 10
                """,
                (start_text, end_text),
            ).fetchall()
            source_health = connection.execute(
                """
                SELECT source,
                       COUNT(*) AS checks,
                       SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS successes,
                       SUM(item_count) AS item_count,
                       ROUND(AVG(latency_ms), 0) AS avg_latency_ms,
                       MAX(CASE WHEN status != 'ok' THEN error ELSE '' END) AS last_error
                FROM source_runs
                WHERE run_date BETWEEN ? AND ?
                GROUP BY source
                ORDER BY successes DESC, item_count DESC, source
                """,
                (start_text, end_text),
            ).fetchall()
            feedback_rows = connection.execute(
                """
                SELECT f.action, COUNT(*) AS count
                FROM feedback f
                WHERE substr(f.created_at, 1, 10) BETWEEN ? AND ?
                GROUP BY f.action
                ORDER BY count DESC
                """,
                (start_text, end_text),
            ).fetchall()
            preference_rows = connection.execute(
                """
                SELECT i.category, i.source, f.action
                FROM feedback f
                JOIN items i ON i.item_key = f.item_key
                WHERE substr(f.created_at, 1, 10) BETWEEN ? AND ?
                """,
                (start_text, end_text),
            ).fetchall()

        category_scores: Dict[str, int] = {}
        source_scores: Dict[str, int] = {}
        for row in preference_rows:
            weight = FEEDBACK_WEIGHTS.get(row["action"], 0)
            category = str(row["category"] or "")
            source = str(row["source"] or "")
            if category:
                category_scores[category] = category_scores.get(category, 0) + weight
            if source:
                source_scores[source] = source_scores.get(source, 0) + weight

        health = []
        for row in source_health:
            item = dict(row)
            checks = int(item["checks"] or 0)
            successes = int(item["successes"] or 0)
            item["success_rate"] = round(successes * 100 / checks) if checks else 0
            health.append(item)
        return {
            "period": {
                "start": start_text,
                "end": end_text,
                "days": days,
            },
            "top_items": [dict(row) for row in top_items],
            "source_health": health,
            "feedback": {row["action"]: row["count"] for row in feedback_rows},
            "preferences": {
                "categories": sorted(
                    category_scores.items(), key=lambda row: row[1], reverse=True
                ),
                "sources": sorted(
                    source_scores.items(), key=lambda row: row[1], reverse=True
                ),
            },
        }
