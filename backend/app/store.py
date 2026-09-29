"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
另带一份 JSON 落盘（data/store.json）：登记或动作提交后立即快照，
这样刷新页面、重启服务后操作结果也不丢失，存量记录也不会被改乱。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORE_FILE = DATA_DIR / "store.json"


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = self._load()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        """优先加载落盘快照；快照缺失或损坏时回退到示例数据。"""
        if STORE_FILE.exists():
            try:
                data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict) and all(isinstance(rows, list) for rows in data.values()):
                    return {name: [dict(row) for row in rows] for name, rows in data.items()}
            except (json.JSONDecodeError, OSError):
                pass
        return {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def commit(self) -> None:
        """把当前各模块数据原子化快照落盘，保证操作结果刷新不丢失。"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix="store-", suffix=".json", dir=DATA_DIR)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._tables, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_name, STORE_FILE)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
