#!/usr/bin/env python3
"""
FastAPI Web Wrapper for Project Risk Pipeline.
Exposes an HTTP POST endpoint for n8n to trigger weekly audits.
"""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cli_runner import DEFAULT_QUESTION, run_pipeline

# Configure standard stdout logging for Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Project Risk Auditor API")


class AuditRequest(BaseModel):
    project: str
    question: str = DEFAULT_QUESTION


@app.post("/run-audit")
async def trigger_audit(req: AuditRequest):
    try:
        results = await run_pipeline(project=req.project, question=req.question)
        return results
    except Exception as e:
        logger.error(
            "Error occurred while running pipeline for project '%s': %s",
            req.project,
            str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    # Runs the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
