import os
from langchain_openai import AzureChatOpenAI

class ChatModels(object):
    deep_seek = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
    gpt_4 = "gpt-4"
    gpt_4_1106_Preview = "gpt-4-1106-Preview"
    gpt_4_32k = "gpt-4-32k"
    gpt_4_turbo_2024_04_09 = "gpt-4-turbo-2024-04-09"
    gpt_4_vision_preview = "gpt-4-vision-preview"
    gpt_4o_2024_05_13 = "gpt-4o-2024-05-13"
    gpt_4o_2024_08_06 = "gpt-4o-2024-08-06"
    gpt_4o_mini_2024_07_18 = "gpt-4o-mini-2024-07-18"
    o3_mini = "o3-mini-2025-01-31"
    text_davinci = "text-davinci-003"
    text_embedding_3_large = "text-embedding-3-large"
    text_embedding_ada = "text-embedding-ada-002"

class UiPathChat(AzureChatOpenAI):
    def __init__(self, token = None, model_name = "gpt-4o-mini-2024-07-18", http_client = None, api_version = "2023-03-15-preview"):
        llm_gateway_pattern = os.getenv("UIPATH_LLMGATEWAY_ENDPOINT_FORMAT") or "https://cloud.uipath.com/{orgId}/{tenantId}/llmgateway_/"
        orgId = os.getenv("UIPATH_ORGANIZATION_ID")
        tenantId = os.getenv("UIPATH_TENANT_ID")
        token = token or os.getenv("UIPATH_LLM_GATEWAY_ACCESS_TOKEN")

        endpoint = llm_gateway_pattern.format(orgId = orgId, tenantId = tenantId)

        super().__init__(azure_endpoint = endpoint, azure_deployment = model_name, model_name = model_name, default_headers = { 
            "X-UIPATH-STREAMING-ENABLED": "false", 
            "Authorization": "Bearer " + token,
            "X-UiPath-LlmGateway-RequestingProduct": "agents",
            "X-UiPath-LlmGateway-RequestingFeature": "langgraph-agent"
        }, http_client=http_client, api_key="none", api_version=api_version)