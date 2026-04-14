from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from datum.services.templates import get_template, list_templates, render_template

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("")
async def api_list_templates():
    return list_templates()


@router.get("/{name}")
async def api_get_template(name: str):
    template = get_template(name)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    return template


@router.get("/{name}/render")
async def api_render_template(name: str, title: str = Query("Untitled")):
    template = get_template(name)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    return {
        "content": render_template(name, title),
        "doc_type": template["doc_type"],
        "default_folder": template["default_folder"],
    }
