"""锅炉设备业务规则：状态流转、字段校验、筛选口径与操作记录都收在这里。

前后端约定（与 boiler/index.vue 对齐）：
- 动作请求体直接是 {"action": "办理投用"}；
- 列表/导出的过滤参数用展示列中文名（设备编号/设备名称/额定蒸发量）；
- 对外展示的状态列统一取内部 status，动作成功后两边同步，避免列表与实际不符。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "boiler"
REQUIRED_FIELDS = ["设备编号", "设备名称", "额定蒸发量"]
DISPLAY_FIELDS = ["设备编号", "设备名称", "额定蒸发量", "工作压力", "使用场所", "投用日期", "下次检验日", "设备状态"]
FILTER_FIELDS = ["设备编号", "设备名称", "额定蒸发量"]
STATUS_ORDER = ["待投用", "在用运行", "停炉检修", "已报废"]
# 每个状态允许执行的动作，以及动作到达的目标状态；不在表里的流转一律拦截。
STATE_MACHINE = {
    "待投用": {"办理投用": "在用运行"},
    "在用运行": {"安排检修": "停炉检修", "报废设备": "已报废"},
    "停炉检修": {"办理投用": "在用运行", "报废设备": "已报废"},
    "已报废": {},
}


class BoilerService:
    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """按展示列模糊检索并按状态精确过滤；返回的行统一走展示口径。"""
        filters = filters or {}
        rows = store.rows(MODULE)
        for field in FILTER_FIELDS:
            keyword = str(filters.get(field) or "").strip()
            if keyword:
                rows = [row for row in rows if keyword in str(row.get(field, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows.sort(key=lambda row: int(row.get("id", 0)))
        total = len(rows)
        start = max(page - 1, 0) * size
        items = [self._to_view(row) for row in rows[start:start + size]]
        return items, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._to_view(entry) if entry is not None else None

    def get_history(self, entry_id: int) -> list[dict[str, Any]] | None:
        if store.find(MODULE, entry_id) is None:
            return None
        return store.history(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in DISPLAY_FIELDS if field != "设备状态"})
        entry["status"] = STATUS_ORDER[0]
        entry["设备状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        store.save()
        return self._to_view(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str, bool]:
        """执行动作，返回 (明细, 说明, 是否业务成功)。

        非法动作或当前状态不允许的流转会被拦下：不改设备状态、不写操作记录。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"锅炉设备 {entry_id} 不存在或已归档", False
        action = (action or "").strip()
        allowed = STATE_MACHINE.get(str(entry.get("status")), {})
        if action not in allowed:
            if not action or action not in {"办理投用", "安排检修", "报废设备"}:
                return None, f"动作「{action}」不属于锅炉设备可执行范围", False
            return None, f"锅炉设备当前为「{entry.get('status')}」，不能执行「{action}」", False
        from_status = str(entry["status"])
        target = allowed[action]
        entry["status"] = target
        entry["设备状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        store.add_history(
            module=MODULE,
            entry_id=entry_id,
            action=action,
            from_status=from_status,
            to_status=target,
        )
        store.save()
        return self._to_view(entry), f"锅炉设备已{action}", True

    @staticmethod
    def _to_view(row: dict[str, Any]) -> dict[str, Any]:
        """对外只暴露列表约定的字段：id 加上八列展示字段，状态列与内部状态同步。"""
        view = {"id": row.get("id")}
        for field in DISPLAY_FIELDS:
            view[field] = row.get("status") if field == "设备状态" else row.get(field)
        return view
