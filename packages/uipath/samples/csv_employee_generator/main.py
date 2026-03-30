"""CSV Employee Generator Agent.

This agent generates employee data in CSV format based on the department and count.
"""

from pydantic import BaseModel


class Input(BaseModel):
    """Input schema for employee generation."""

    department: str
    count: int = 3


class Output(BaseModel):
    """Output schema with CSV data."""

    csv_data: str


def main(input: Input) -> Output:
    """Generate employee CSV data based on department and count.

    Args:
        input: Request with department and count

    Returns:
        Output with CSV formatted employee data
    """
    # Employee database by department
    employees_by_dept = {
        "Engineering": [
            ("Alice Johnson", 28, "Software Engineer"),
            ("Bob Smith", 32, "Senior Engineer"),
            ("Carol Davis", 26, "DevOps Engineer"),
            ("David Wilson", 35, "Tech Lead"),
            ("Eve Martinez", 29, "QA Engineer"),
        ],
        "Sales": [
            ("Frank Brown", 30, "Sales Rep"),
            ("Grace Lee", 27, "Account Manager"),
            ("Henry Taylor", 33, "Sales Director"),
            ("Ivy Chen", 25, "Sales Associate"),
            ("Jack Kumar", 31, "Regional Manager"),
        ],
        "HR": [
            ("Kelly White", 34, "HR Manager"),
            ("Liam Garcia", 28, "Recruiter"),
            ("Maya Patel", 29, "HR Specialist"),
            ("Noah Johnson", 32, "Training Coordinator"),
            ("Olivia Rodriguez", 26, "HR Assistant"),
        ],
    }

    # Get employees for the requested department
    department = input.department
    count = min(input.count, 5)  # Max 5 employees per department

    if department not in employees_by_dept:
        # Return empty result for unknown department
        csv_lines = ["Name,Age,Role"]
        return Output(csv_data="\n".join(csv_lines))

    employees = employees_by_dept[department][:count]

    # Generate CSV
    csv_lines = ["Name,Age,Role"]
    for name, age, role in employees:
        csv_lines.append(f"{name},{age},{role}")

    return Output(csv_data="\n".join(csv_lines))
