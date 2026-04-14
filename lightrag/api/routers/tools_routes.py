"""
API routes for Excel Tools feature.

Provides endpoints for uploading Excel files, creating/listing/deleting
tools, and searching tool data.
"""

import uuid
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from lightrag.api.utils_api import get_combined_auth_dependency
from lightrag.tools.excel_tool_manager import (
    ExcelToolManager,
    ToolDefinition,
    ToolParameter,
    parse_excel_file,
)

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolParameterRequest(BaseModel):
    column_name: str
    param_name: str
    param_description: str


class CreateToolRequest(BaseModel):
    file_id: str
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    parameters: list[ToolParameterRequest]


class SearchRequest(BaseModel):
    params: dict[str, str]
    top_k: int = Field(default=10, ge=1, le=100)


def create_tools_routes(
    tool_manager: ExcelToolManager,
    api_key: Optional[str] = None,
):
    combined_auth = get_combined_auth_dependency(api_key)

    @router.post("/upload", dependencies=[Depends(combined_auth)])
    async def upload_excel(file: UploadFile = File(...)):
        """Upload an Excel file and extract column names."""
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        try:
            contents = await file.read()
            buf = io.BytesIO(contents)
            columns, rows, row_count = parse_excel_file(buf, file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        file_id = str(uuid.uuid4())
        await tool_manager.store_temp_upload(file_id, columns, rows)

        return {
            "columns": columns,
            "row_count": row_count,
            "file_id": file_id,
        }

    @router.post("", status_code=201, dependencies=[Depends(combined_auth)])
    async def create_tool(request: CreateToolRequest):
        """Create a tool definition from an uploaded file."""
        upload_data = await tool_manager.get_temp_upload(request.file_id)
        if not upload_data:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired file_id. Please upload the file again.",
            )

        tool_params = [
            ToolParameter(
                column_name=p.column_name,
                param_name=p.param_name,
                param_description=p.param_description,
            )
            for p in request.parameters
        ]

        search_columns = [p.column_name for p in request.parameters]

        tool_def = ToolDefinition(
            tool_id=str(uuid.uuid4()),
            name=request.name,
            description=request.description,
            parameters=tool_params,
            column_names=upload_data["columns"],
            search_columns=search_columns,
            row_count=len(upload_data["rows"]),
        )

        try:
            created = await tool_manager.create_tool(tool_def, upload_data["rows"])
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

        return {
            "tool_id": created.tool_id,
            "name": created.name,
            "description": created.description,
            "parameters": [
                {
                    "column_name": p.column_name,
                    "param_name": p.param_name,
                    "param_description": p.param_description,
                }
                for p in created.parameters
            ],
            "row_count": created.row_count,
            "created_at": created.created_at,
        }

    @router.get("", dependencies=[Depends(combined_auth)])
    async def list_tools():
        """List all registered tools."""
        tools = await tool_manager.list_tools()
        return {"tools": tools}

    @router.delete("/{tool_id}", dependencies=[Depends(combined_auth)])
    async def delete_tool(tool_id: str):
        """Delete a tool and its data."""
        meta = await tool_manager.get_tool(tool_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Tool not found")

        await tool_manager.delete_tool(tool_id)
        return {"deleted": True, "tool_id": tool_id}

    @router.post("/{tool_id}/search", dependencies=[Depends(combined_auth)])
    async def search_tool(tool_id: str, request: SearchRequest):
        """Search tool data (called internally by LLM tool execution)."""
        meta = await tool_manager.get_tool(tool_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Tool not found")

        rows = await tool_manager.search(
            tool_id, request.params, top_k=request.top_k
        )
        return {"rows": rows, "total_matches": len(rows)}

    return router
