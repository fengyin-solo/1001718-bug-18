"""锅炉设备业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "boiler"
REQUIRED_FIELDS = ["设备编号", "设备名称", "额定蒸发量"]
OPTIONAL_FIELDS = ["工作压力", "使用场所", "投用日期", "下次检验日"]
STATUS_ORDER = ["待投用", "在用运行", "停炉检修", "已报废"]
TERMINAL_STATUS = "已报废"

# 状态流转表：当前状态 -> [(动作, 目标状态)]，动作只能沿表中路径执行，
# 跨状态、逆向、终态上的动作一律判为非法。
FLOW: dict[str, list[tuple[str, str]]] = {
    "待投用": [("办理投用", "在用运行")],
    "在用运行": [("安排检修", "停炉检修"), ("报废设备", "已报废")],
    "停炉检修": [("恢复投用", "在用运行"), ("报废设备", "已报废")],
    "已报废": [],
}


def _pairs(status: str) -> list[tuple[str, str]]:
    return FLOW.get(status, [])


def allowed_actions(status: str) -> list[str]:
    """当前状态下允许执行的动作名称，供列表行内按钮与接口校验共用同一口径。"""
    return [action for action, _ in _pairs(status)]


class BoilerService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设备编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = rows[start:start + size]
        return [self._view(row) for row in page_rows], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._view(row) if row is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in [*REQUIRED_FIELDS, *OPTIONAL_FIELDS]:
            if values.get(field) is not None:
                entry[field] = values[field]
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["records"] = [
            {
                "action": "登记入库",
                "from_status": None,
                "to_status": STATUS_ORDER[0],
                "time": date.today().isoformat(),
                "note": "新设备登记入库",
            }
        ]
        rows.append(entry)
        store.commit()
        return self._view(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"锅炉设备 {entry_id} 不存在或已归档"
        current = str(entry.get("status") or "")
        target = next((to for act, to in _pairs(current) if act == action), None)
        if target is None:
            allowed = "、".join(allowed_actions(current)) or "无（已报废为终态）"
            return None, f"动作「{action}」在当前状态「{current}」下不可执行，当前状态可执行：{allowed}"
        entry["status"] = target
        entry["pending"] = target != TERMINAL_STATUS
        entry["abnormal"] = False
        entry.setdefault("records", []).append({
            "action": action,
            "from_status": current,
            "to_status": target,
            "time": date.today().isoformat(),
            "note": f"锅炉设备{action}",
        })
        store.commit()
        return self._view(entry), f"锅炉设备已{action}"

    def list_records(self, entry_id: int) -> list[dict[str, Any]] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return list(entry.get("records", []))

    @staticmethod
    def _view(row: dict[str, Any]) -> dict[str, Any]:
        """列表/详情统一视图：附带当前状态可执行动作，供前端按状态渲染按钮。"""
        view = dict(row)
        view["actions"] = allowed_actions(str(row.get("status") or ""))
        return view
