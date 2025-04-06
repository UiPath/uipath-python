from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import re
# Set up the Tavily search tool
tavily_tool = TavilySearchResults(max_results=5)

# Define system prompt
with open("state-specific-validation.py", "r") as file:
  state_specific_rules = file.read()

system_prompt = f"""You are an advanced Loan Validation Agent designed to perform thorough checks on loan applications across all U.S. states. Your primary function is to validate information provided in JSON format and ensure consistency, going beyond basic automated form checks.

For each loan application, you will:

1. Parse the provided JSON input, which contains all necessary information about the applicant and their documents.

2. Identify the applicant's state of residence from the JSON data.

3. Perform the following general checks for all states:
  - Verify that the name on all documents matches the applicant's name exactly, including any suffixes or middle initials.
  - Confirm that pay stubs, bank statements, or W-2 forms are recent (typically within the last 60-90 days, or from the current/previous year for W-2s).
  - Cross-verify the annual or monthly income stated in documents against the typed income in the portal.
  - Ensure that the address on documents matches the portal-entered address.
  - Check that all required documents are present and their metadata indicates they are complete and legible.
  - Verify that signatures on documents match the applicant's name (if available).
  - Confirm that employer information on documents is consistent with the portal data.
  - Validate that document metadata and capture dates are recent and within acceptable ranges (usually 60-90 days).

4. Apply state-specific validation rules based on the applicant's state:
{state_specific_rules}

5. Handle discrepancies and inconsistencies:
  - Flag any mismatches between document information and portal-entered data.
  - Identify inconsistencies across different documents.
  - Report any missing or incomplete information required for the specific state.
  - Highlight potential red flags or unusual patterns in the application data.

6. Error handling and incomplete information:
  - If critical information is missing from the JSON input, clearly state what is needed to complete the validation.
  - For inconsistent information, provide details on the conflicting data points.
  - Suggest additional documentation or clarification needed from the applicant when necessary.

7. Provide a detailed validation report in the following format:
  {{
  "validation_report": {{
   "is_valid": boolean,
   "general_checks": {{
    // Results of general validation checks
   }},
   "state_specific_checks": {{
    // Results of state-specific validation checks
   }},
   "discrepancies": [
    // List of found discrepancies or issues
   ],
   "recommendations": [
    // List of recommendations for further action
   ]
  }},
  "explanation": "Detailed explanation of the validation process and findings"
  }}

Remember, your role is crucial in ensuring the accuracy and legitimacy of loan applications. Be thorough, detail-oriented, and always adhere to the specific guidelines for each state.

When you receive a loan application JSON, analyze the provided information to perform these checks. Then, proceed with your validation process and provide a comprehensive report.

To accomplish these tasks, follow these steps:
1. Use the TavilySearchResults tool to find recent and relevant information about the company.
2. Analyze the collected data to form insights about the company's structure, key decision-makers, and potential outreach strategies.

When using the search tool:
- Clearly state the purpose of each search.
- Formulate effective search queries to find specific information about different aspects of the company.
- If a search doesn't provide the expected information, try refining your query.

When responding, structure your output as a comprehensive analysis. Use clear section headers to organize the information. Provide concise, actionable insights. If you need more information to complete any part of your analysis, clearly state what additional details would be helpful.

Always maintain a professional and objective tone in your research and recommendations. Your goal is to provide accurate, valuable information that can be used to inform business decisions and outreach efforts.

DO NOT do any math as specified in your instructions.
"""

llm = ChatAnthropic(model="claude-3-5-sonnet-latest")

research_agent = create_react_agent(llm, tools=[tavily_tool], prompt=system_prompt)



class Address(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str

class TypedInfo(BaseModel):
    name: str
    address: Address
    email: str
    phone: str
    employment_status: str
    employer_name: str
    annual_income: int
    monthly_income: int
    credit_score: int
    residency_duration_years: int
    portal_document_status: str

class DocumentMetadata(BaseModel):
    issue_state: Optional[str] = None
    name_on_doc: Optional[str] = None
    expiration_date: Optional[str] = None
    signature_sample: Optional[str] = None
    doc_quality: Optional[str] = None
    capture_date: Optional[str] = None
    pay_period_end: Optional[str] = None
    net_pay: Optional[int] = None
    employer_address: Optional[str] = None
    doc_date: Optional[str] = None
    account_holder: Optional[str] = None
    statement_date: Optional[str] = None
    address_on_statement: Optional[str] = None
    pages_scanned: Optional[int] = None
    insured_property_address: Optional[str] = None
    policy_expiration: Optional[str] = None
    coverage_amount: Optional[int] = None

class UploadedDocument(BaseModel):
    doc_type: str
    doc_name: str
    doc_metadata: DocumentMetadata

class ApplicantData(BaseModel):
    typed_info: TypedInfo
    uploaded_documents: List[UploadedDocument]

class LoanRequest(BaseModel):
    amount_requested: int
    purpose: str
    term_years: int
    interest_rate: float

class ReviewDisplay(BaseModel):
    summary: str
    additional_metadata: str

class GraphInput(BaseModel):
    application_id: str
    submission_timestamp: str
    applicant: ApplicantData
    loan_request: LoanRequest
    review_display: ReviewDisplay


class Report(BaseModel):
    is_valid: bool
    general_checks: Dict[str, Any]
    state_specific_checks: Dict[str, Any]
    discrepancies: List[str]
    recommendations: List[str]

class GraphOutput(BaseModel):
    response: Report


def research_node(state: GraphInput) -> GraphOutput:
    # Format the user message with the company name
    user_message = f"""Please validate the following loan application using the provided input data: {state}     

        Please perform all necessary general and state-specific validation checks as per your guidelines. Pay special attention to the state-specific requirements for {{state}}. Provide a detailed report of your findings, including any discrepancies or issues found, and recommendations for further action if needed.

        If any critical information is missing or inconsistent, please highlight it in your report and suggest what additional information or clarification is needed from the applicant.
    """

    new_state = MessagesState(messages=[{"role": "user", "content": user_message}])

    result = research_agent.invoke(new_state)
    print("=======================result==============================")
    print(result)
    print("=======================result==============================")
    print("=====================content================================")
    print(result["messages"][-1].content)
    print("======================content===============================")

    try:
      ai_message_content = result["messages"][-1].content
      json_match = re.search(r'\{.*\}', ai_message_content, re.DOTALL)
      json_content = json_match.group(0)  # Extract the JSON string
      parsed_json = json.loads(json_content)  # Parse the JSON      
      # Parse the AI's response into GraphOutput
      # Assuming the AI's response is in JSON format, we can parse it
      # This will raise an exception if the format is incorrect
      # Note: Ensure the AI's response is in the expected format before parsing
      validation_report = parsed_json["validation_report"]
      print("======================validation_report===============================")
      print(validation_report)
      print("=====================validation_report================================")
      return GraphOutput(response=validation_report)
    except Exception as e:
        # Handle the case where the result cannot be parsed into GraphOutput
        print(f"Error processing research node: {e}")
        return GraphOutput(response=Report(
            is_valid=False,
            general_checks={},
            state_specific_checks={},
            discrepancies=["Failed to generate report"],
            recommendations=[]
        ))


# Build the state graph
builder = StateGraph(input=GraphInput, output=GraphOutput)
builder.add_node("researcher", research_node)

builder.add_edge(START, "researcher")
builder.add_edge("researcher", END)

# Compile the graph
graph = builder.compile()
