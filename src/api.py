#!/usr/bin/env python3
"""
FastAPI Web Wrapper for Project Risk Pipeline.
Exposes an HTTP POST endpoint for n8n to trigger weekly audits.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cli_runner import run_pipeline, DEFAULT_QUESTION

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
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__": # pragma: no cover
    import uvicorn
    # Runs the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)