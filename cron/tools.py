"""Cron 管理工具：agent 通过工具增删查定时任务。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tools.base_tool import BaseTool

if TYPE_CHECKING:
    from .scheduler import CronScheduler


class CronAddTool(BaseTool):
    name = "cron_add"
    description = (
        "Add a scheduled cron job. The prompt will be injected as a user "
        "message when the cron expression matches. Returns the job ID."
    )

    def __init__(self, scheduler: "CronScheduler") -> None:
        self.scheduler = scheduler

    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "cron": {
                    "type": "string",
                    "description": "Five-field cron: min hour dom month dow",
                },
                "prompt": {"type": "string"},
                "recurring": {"type": "boolean"},
                "durable": {"type": "boolean"},
            },
            "required": ["cron", "prompt"],
        }

    def execute(
        self, cron: str, prompt: str,
        recurring: bool = True, durable: bool = True,
    ) -> str:
        job_id, err = self.scheduler.add_job(cron, prompt, recurring, durable)
        if err:
            return err
        return f"Added {job_id}: {cron} -> {prompt[:50]}"

    def preview(self, tool_input) -> str:
        return f"cron_add {tool_input.get('cron', '')}"


class CronListTool(BaseTool):
    name = "cron_list"
    description = "List all scheduled cron jobs with ID, cron, prompt, status."

    def __init__(self, scheduler: "CronScheduler") -> None:
        self.scheduler = scheduler

    def input_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self) -> str:
        jobs = self.scheduler.list_jobs()
        if not jobs:
            return "No cron jobs."
        lines = []
        for j in jobs:
            rec = "recurring" if j.recurring else "once"
            dur = "durable" if j.durable else "volatile"
            lines.append(
                f"{j.id}  [{rec}/{dur}]  {j.cron}  ->  {j.prompt[:60]}"
            )
        return "\n".join(lines)

    def preview(self, tool_input) -> str:
        return "cron_list"


class CronRemoveTool(BaseTool):
    name = "cron_remove"
    description = "Remove a cron job by ID."

    def __init__(self, scheduler: "CronScheduler") -> None:
        self.scheduler = scheduler

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
        }

    def execute(self, job_id: str) -> str:
        ok = self.scheduler.remove_job(job_id)
        return f"Removed {job_id}" if ok else f"Job {job_id} not found"

    def preview(self, tool_input) -> str:
        return f"cron_remove {tool_input.get('job_id', '')}"


def build_cron_tools(scheduler: "CronScheduler") -> list[BaseTool]:
    return [
        CronAddTool(scheduler),
        CronListTool(scheduler),
        CronRemoveTool(scheduler),
    ]
