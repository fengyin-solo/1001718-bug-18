"""锅炉设备接口：维护锅炉设备，覆盖办理投用、安排检修、报废设备等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.boiler import BoilerService

router = APIRouter(prefix="/api/boiler", tags=["锅炉设备"])

service = BoilerService()

LIST_FIELDS = ["设备编号", "设备名称", "额定蒸发量", "工作压力", "使用场所", "投用日期", "下次检验日", "设备状态"]
STATUSES = ["待投用", "在用运行", "停炉检修", "已报废"]


class ActionPayload(BaseModel):
    """行内动作报文：前端直接提交动作名 {"action": "办理投用"}。"""

    action: str = ""


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按设备编号检索（兼容旧参数）"),
    status: str | None = Query(default=None, description="待投用、在用运行、停炉检修、已报废"),
    page: int = 1,
    size: int = 20,
    设备编号: str | None = None,
    设备名称: str | None = None,
    额定蒸发量: str | None = None,
) -> PageResult[dict]:
    """按展示列与状态过滤锅炉设备列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    filters = {"设备编号": 设备编号 or keyword or "", "设备名称": 设备名称 or "", "额定蒸发量": 额定蒸发量 or ""}
    items, total = service.list_entries(filters=filters, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


# 注意：/export 必须在 /{entry_id} 之前注册，否则会被当成设备 id 解析而报 422。
@router.get("/export")
def export_entries(
    keyword: str | None = None,
    status: str | None = None,
    设备编号: str | None = None,
    设备名称: str | None = None,
    额定蒸发量: str | None = None,
) -> dict[str, Any]:
    """导出锅炉设备清单：口径与列表一致，返回当前过滤条件下的全量数据。"""
    filters = {"设备编号": 设备编号 or keyword or "", "设备名称": 设备名称 or "", "额定蒸发量": 额定蒸发量 or ""}
    items, total = service.list_entries(filters=filters, status=status, page=1, size=10000)
    return {"module": "boiler", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条锅炉设备明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"锅炉设备 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/history")
def get_history(entry_id: int) -> dict[str, Any]:
    """读取单条锅炉设备的操作记录；记录只追加，不提供修改入口。"""
    history = service.get_history(entry_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"锅炉设备 {entry_id} 不存在或已归档")
    return {"module": "boiler", "entry_id": entry_id, "total": len(history), "items": history}


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条锅炉设备，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="锅炉设备已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    """对单条锅炉设备执行办理投用、安排检修、报废设备；非法动作或当前状态不允许的流转会被拦下。"""
    entry, message, ok = service.run_action(entry_id, payload.action)
    return ActionResult(ok=ok, message=message, entry=entry)
