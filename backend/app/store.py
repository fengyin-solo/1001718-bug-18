"""数据仓库：启动时从本地存档加载，没有存档则用示例数据初始化。

示例实现原本只放在内存里，重启/换进程后动作结果就丢了。现在把各业务表和
操作记录统一落到一个 JSON 文件里：动作成功后追加记录并落盘，刷新页面或重启
服务都能读到最新结果。操作记录只追加、不回改，避免把存量记录改乱。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

HISTORY_TABLE = "history"
DATA_FILE = Path(
    os.environ.get("APP_DATA_FILE", str(Path(__file__).resolve().parent.parent / "data" / "store.json"))
)


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._loaded = False

    def _bootstrap(self) -> None:
        """首次加载：优先读本地存档；存档不存在时按示例数据初始化。"""
        if DATA_FILE.exists():
            with DATA_FILE.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self._tables = {name: [dict(row) for row in rows] for name, rows in payload.items()}
            self._tables.setdefault(HISTORY_TABLE, [])
            return
        self._tables = {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}
        self._tables[HISTORY_TABLE] = []
        # 锅炉设备是这次治理的存量数据：把已有设备按采集顺序回填成操作记录，
        # 并保证对外展示的「设备状态」与内部状态一致。
        self._backfill_boiler_history()
        self.save()

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            # 先置位再初始化：bootstrap 过程中会回调 rows/add_history，避免重复进入。
            self._loaded = True
            self._bootstrap()

    def save(self) -> None:
        """把当前全部表原子落盘，避免写到一半被读到半截文件。"""
        self._ensure_loaded()
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
        with tmp_file.open("w", encoding="utf-8") as handle:
            json.dump(self._tables, handle, ensure_ascii=False, indent=2)
        tmp_file.replace(DATA_FILE)

    def module_names(self) -> list[str]:
        self._ensure_loaded()
        return sorted(name for name in self._tables if name != HISTORY_TABLE)

    def rows(self, module: str) -> list[dict[str, Any]]:
        self._ensure_loaded()
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def history(self, module: str, entry_id: int | None = None) -> list[dict[str, Any]]:
        """读取操作记录：可限定模块，可再限定到单条设备。记录只追加、不修改。"""
        self._ensure_loaded()
        records = self._tables.setdefault(HISTORY_TABLE, [])
        result = [record for record in records if record.get("module") == module]
        if entry_id is not None:
            result = [record for record in result if int(record.get("entry_id", 0)) == entry_id]
        return result

    def add_history(
        self,
        *,
        module: str,
        entry_id: int,
        action: str,
        from_status: str | None,
        to_status: str,
        operator: str | None = None,
        source: str = "action",
        operated_at: str | None = None,
    ) -> dict[str, Any]:
        """追加一条操作记录。时间缺省取当前时间，回填场景可显式传入采集时间。"""
        self._ensure_loaded()
        records = self._tables.setdefault(HISTORY_TABLE, [])
        record = {
            "id": max((int(record.get("id", 0)) for record in records), default=0) + 1,
            "module": module,
            "entry_id": entry_id,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "operator": operator,
            "source": source,
            "operated_at": operated_at or datetime.now().isoformat(timespec="seconds"),
        }
        records.append(record)
        return record

    def _backfill_boiler_history(self) -> None:
        """锅炉存量数据按采集顺序（id 升序）回填状态流转记录。

        每条设备按「待投用 → 在用运行 → 停炉检修 → 已报废」的顺序，把到达当前
        状态所经过的动作依次补成记录；待投用的设备没有可回填的动作。
        """
        transitions = ["办理投用", "安排检修", "报废设备"]
        status_chain = ["待投用", "在用运行", "停炉检修", "已报废"]
        for row in sorted(self.rows("boiler"), key=lambda item: int(item.get("id", 0))):
            current = str(row.get("status") or "")
            row["设备状态"] = current
            if current not in status_chain:
                continue
            steps = status_chain.index(current)
            for index in range(steps):
                self.add_history(
                    module="boiler",
                    entry_id=int(row["id"]),
                    action=transitions[index],
                    from_status=status_chain[index],
                    to_status=status_chain[index + 1],
                    source="backfill",
                    operated_at=row.get("投用日期"),
                )

    def overview(self) -> dict[str, object]:
        self._ensure_loaded()
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
