"""锅炉设备接口：维护锅炉设备，覆盖办理投用、安排检修、报废设备等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.boiler import BoilerService

router = APIRouter(prefix="/api/boiler", tags=["锅炉设备"])

service = BoilerService()

LIST_FIELDS = ["设备编号", "设备名称", "额定蒸发量", "工作压力", "使用场所", "投用日期", "下次检验日", "设备状态"]
STATUSES = ["待投用", "在用运行", "停炉检修", "已报废"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按设备编号检索"),
    status: str | None = Query(default=None, description="待投用、在用运行、停炉检修、已报废"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按设备编号与状态过滤锅炉设备列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按设备编号检索"),
    status: str | None = Query(default=None, description="待投用、在用运行、停炉检修、已报废"),
) -> dict[str, Any]:
    """导出锅炉设备清单：口径与列表一致，返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(keyword=keyword, status=status, page=1, size=10000)
    return {"module": "boiler", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条锅炉设备明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"锅炉设备 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/records")
def list_entry_records(entry_id: int) -> dict[str, Any]:
    """读取单条锅炉设备的流转记录（动作留痕）；设备不存在时给出可读错误。"""
    records = service.list_records(entry_id)
    if records is None:
        raise HTTPException(status_code=404, detail=f"锅炉设备 {entry_id} 不存在或已归档")
    return {"module": "boiler", "id": entry_id, "items": records}


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条锅炉设备，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="锅炉设备已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条锅炉设备执行办理投用、安排检修、恢复投用、报废设备；
    动作参数统一放在 values 里，不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
