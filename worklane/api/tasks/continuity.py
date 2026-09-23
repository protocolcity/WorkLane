"""HTTP access to the same explicit, signed continuity operations as MCP."""
from fastapi import Request
from fastapi.responses import JSONResponse
from worklane.api.tasks._router import router
from worklane.mcp.handlers import TPHandlers, ToolError, dispatch_tool


async def _operation(request, task_id, tool):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("request must be an object")
        author = payload.pop("author", "")
        project = payload.get("project")
        if not isinstance(author, str) or not author.strip() or not project:
            raise ValueError("author and explicit project are required")
        payload["task_id"] = task_id
        result = dispatch_tool(TPHandlers(author=author), tool, payload)
        return JSONResponse(result)
    except (ValueError, TypeError, ToolError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


@router.post("/api/admin/tasks/{task_id}/checkpoint")
async def checkpoint(request: Request, task_id: str):
    return await _operation(request, task_id, "wl_checkpoint")


@router.post("/api/admin/tasks/{task_id}/claim")
async def claim(request: Request, task_id: str):
    return await _operation(request, task_id, "wl_claim")


@router.post("/api/admin/tasks/{task_id}/handoff")
async def handoff(request: Request, task_id: str):
    return await _operation(request, task_id, "wl_handoff")
