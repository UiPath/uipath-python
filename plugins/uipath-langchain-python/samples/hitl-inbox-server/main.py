from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import httpx
import uuid
from datetime import datetime
from uipath import UiPath

# Database models and setup
from database import SessionLocal, engine
import models
import schemas

sdk = UiPath()

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Open Deep Research")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API endpoint to submit a new job
@app.post("/api/submit-job", response_model=schemas.JobResponse)
async def submit_job(job_request: schemas.JobRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Create a new job record in the database
    job_id = str(uuid.uuid4())
    new_job = models.Job(
        id=job_id,
        topic=job_request.topic,
        status="creating",
        created_at=datetime.now()
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)


    # Submit the job to the external service in the background
    background_tasks.add_task(
        submit_orchestrator_job,
        job_id=job_id,
        topic=job_request.topic,
        db=db
    )

    return {"job_id": job_id, "status": "creating", "message": "Job submitted successfully"}

# Background task to submit job to Orchestrator
async def submit_orchestrator_job(job_id: str, topic: str, db: Session):
    try:
        agent_job = await sdk.processes.invoke_async(
            name="open_deep_research",
            input_arguments={"topic": topic}
        )
        print(agent_job)
        # Update job with Orchestrator job key if provided
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if job and agent_job:
            job.agent_job_key = agent_job.Key
            job.agent_job_id = agent_job.Id
            job.status = "pending"
            db.commit()
        print(job.agent_job_id)

    except httpx.HTTPError as e:
        # If Orchestrator request fails, update the job status
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if job:
            job.status = "faulted"
            job.error_message = str(e)
            db.commit()

# Webhook endpoint for Orchestrator job events notifications
@app.post("/webhook/job-complete")
async def job_complete_webhook(request: Request, db: Session = Depends(get_db)):
    webhook_data = await request.json()
    agent_job = webhook_data.get('Job')
    agent_job_id = agent_job.get('Id')
    #agent_job_key = agent_job.get('Key')

    print(webhook_data)
    print(agent_job_id)
    if not agent_job_id:
        raise HTTPException(status_code=400, detail="Missing Job.Key in webhook data")

    # Retrieve the job from the database
    job = db.query(models.Job).filter(models.Job.agent_job_id == agent_job_id).first()
    if not job:
        return {"status": "faulted", "message": "Job not found"}

    event_type = webhook_data.get('Type')

    print(event_type)

    # Update the job status and save the output
    if event_type == 'job.started':
        job.status = 'running'

    if event_type == 'job.suspended':
        # Create a new inbox message with the job trigger output
        inbox_content = await _retrieve_message_content(job_id=agent_job_id)
        inbox_message = models.InboxMessage(
            id=str(uuid.uuid4()),
            job_id=job.id,
            content=inbox_content,
            status="pending",
            received_at=datetime.now()
        )
        db.add(inbox_message)
        job.status = 'suspended'

    if event_type == 'job.completed':
        output_args = agent_job.get('OutputArguments')
        if output_args is not None:
            job.output = output_args.get('final_report', '')
        else:
            job.output = ''
        job.status = 'completed'

    if event_type == 'job.faulted':
        job.status = 'faulted'

    job.completed_at = datetime.now()

    db.commit()

    return {"status": "success", "message": "Job completion processed successfully"}

# API endpoint to get all inbox messages
@app.get("/api/inbox", response_model=List[schemas.InboxMessageResponse])
async def get_inbox_api(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(models.InboxMessage)

    if status:
        query = query.filter(models.InboxMessage.status == status)

    messages = query.order_by(models.InboxMessage.received_at.desc()).offset(skip).limit(limit).all()
    return messages

# API endpoint to approve a message
@app.post("/api/approve-message/{message_id}", response_model=schemas.MessageApprovalResponse)
async def approve_message_api(
    message_id: str,
    approval_data: schemas.MessageApprovalRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Find the message
    message = db.query(models.InboxMessage).filter(models.InboxMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail=f"Message with id {message_id} not found")

    # Update message status
    message.status = "approved"
    message.approved_at = datetime.now()
    message.human_feedback = approval_data.human_feedback
    db.commit()

    # Find the associated job
    job = db.query(models.Job).filter(models.Job.id == message.job_id).first()
    if job and job.agent_job_id:
        # Resume the job in the background
        background_tasks.add_task(
            resume_orchestrator_job,
            job_id=job.id,
            agent_job_id=job.agent_job_id,
            human_feedback=approval_data.human_feedback,
            db=db
        )
        return {"status": "success", "message": "Message approved and job resumed with human feedback"}

    return {"status": "success", "message": "Message approved with human feedback"}

# Background task to resume an Orchestrator job
async def resume_orchestrator_job(job_id: str, agent_job_id: str, human_feedback: str, db: Session):
    try:
        payload = True if human_feedback.lower() == "true" else human_feedback

        await sdk.jobs.resume_async(job_id=agent_job_id, payload=payload)

        # Update job status
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if job:
            job.status = "resumed"
            job.human_feedback = human_feedback
            db.commit()

    except httpx.HTTPError as e:
        # If the resume request fails, log the error
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if job:
            job.error_message = f"Failed to resume job: {str(e)}"
            db.commit()

# API endpoint to get job status
@app.get("/api/job/{job_id}", response_model=schemas.JobDetailResponse)
async def get_job_status_api(job_id: str, db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with id {job_id} not found")

    # Get associated inbox messages
    messages = db.query(models.InboxMessage).filter(models.InboxMessage.job_id == job_id).all()

    return {
        "id": job.id,
        "topic": job.topic,
        "status": job.status,
        "agent_job_id": job.agent_job_id,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "error_message": job.error_message,
        "human_feedback": job.human_feedback,
        "output": job.output,
        "messages": messages
    }

# API endpoint to get all jobs
@app.get("/api/jobs", response_model=List[schemas.JobBasicResponse])
async def get_jobs_api(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(models.Job)

    if status:
        query = query.filter(models.Job.status == status)

    jobs = query.order_by(models.Job.created_at.desc()).offset(skip).limit(limit).all()
    return jobs

async def _retrieve_message_content(
    job_id: str,
    folder_key: Optional[str] = None,
    folder_path: Optional[str] = None,
) -> str:
    spec = sdk.jobs._retrieve_inbox_id_spec(
        job_id=job_id,
        folder_key=folder_key,
        folder_path=folder_path,
    )
    response = await sdk.jobs.request_async(
        spec.method,
        url=spec.endpoint,
        params={
            "$filter": f"JobId eq {job_id}",
            "$top": 1
        },
        headers=spec.headers,
    )

    response = response.json()
    print(response)
    if len(response["value"]) > 0:
        return response["value"][0]["TriggerConfiguration"]
    else:
        raise Exception("No inbox found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
