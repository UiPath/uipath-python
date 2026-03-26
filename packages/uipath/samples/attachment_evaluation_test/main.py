"""Sample agent that produces a job attachment as output.

This agent demonstrates:
1. Creating content based on input
2. Uploading content as a job attachment
3. Returning the attachment URI for evaluation
"""

from pydantic import BaseModel

from uipath.platform import UiPath


class Input(BaseModel):
    """Input schema for report generation."""

    task: str


class Output(BaseModel):
    """Output schema with attachment URI."""

    report: str
    task: str
    status: str


def main(input_data: Input) -> Output:
    """Create a report and return it as a job attachment.

    Args:
        input_data: Input containing task description

    Returns:
        Output with attachment URI, task, and status
    """
    task = input_data.task

    # Generate report content based on the task
    if "sales" in task.lower():
        content = """Sales Report Q4 2024

Total Revenue: $1,250,000
New Customers: 45
Customer Retention: 92%
Top Product: Enterprise Suite
"""
    elif "inventory" in task.lower():
        content = """Inventory Report

Warehouse A: 1,234 items
Warehouse B: 987 items
Low Stock Items: 12
Reorder Required: 8
"""
    elif "employee" in task.lower():
        content = """Employee Performance Report

Total Employees: 150
Average Performance Score: 4.2/5.0
Training Completed: 95%
Promotions This Quarter: 8
"""
    else:
        # Default generic report
        content = f"""Task Report: {task}

Status: Completed
Date: 2024-03-25
Summary: Task has been successfully completed.
Notes: All requirements met.
"""

    # Upload content as a job attachment
    client = UiPath()
    attachment_id = client.attachments.upload(
        name=f"report_{task.replace(' ', '_')}.txt",
        content=content,
    )

    # Return the attachment URI
    attachment_uri = f"urn:uipath:cas:file:orchestrator:{attachment_id}"

    return Output(
        report=attachment_uri,
        task=task,
        status="completed",
    )
