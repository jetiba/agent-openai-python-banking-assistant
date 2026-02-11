from azure.core.credentials import TokenCredential
from agent_framework.azure import AzureAIProjectAgentOptions, AzureAIProjectAgentProvider
from agent_framework import Agent, MCPStreamableHTTPTool
from app.config.azure_credential import get_azure_credential_async

import logging


logger = logging.getLogger(__name__)

class AccountAgent :
    instructions = """
    you are a personal financial advisor who help the user to retrieve information about their bank accounts.
    Use html list or table to display the account information.
    Always use the below logged user details to retrieve account info:
    {user_mail}
    """
    name = "AccountAgent"
    description = "This agent manages user accounts related information such as balance, credit cards."

    def __init__(self, foundry_project_provider: AzureAIProjectAgentProvider, 
                 chat_deployment_name:str,
                 account_mcp_server_url: str ):
        self.foundry_project_provider = foundry_project_provider
        self.account_mcp_server_url = account_mcp_server_url
        self.chat_deployment_name = chat_deployment_name
        self.created_agent = foundry_project_provider.create_agent(
            model=chat_deployment_name, name=AccountAgent.name, description=AccountAgent.description
        )
        


    async def build_af_agent(self) -> Agent[AzureAIProjectAgentOptions]:

      logger.info("Building request scoped Account agent run ")

      user_mail="bob.user@contoso.com"
      full_instruction = AccountAgent.instructions.format(user_mail=user_mail)

      credential = await get_azure_credential_async()  
          
      
      logger.info("Initializing Account MCP server tools ")
      #await self.account_mcp_server.__aenter__()
      account_mcp_server = MCPStreamableHTTPTool(
        name="Account MCP server client",
        url=self.account_mcp_server_url
     )
      await account_mcp_server.connect()

      agent =   await self.foundry_project_provider.create_agent(
            model=self.chat_deployment_name,
            name=AccountAgent.name, 
            description=AccountAgent.description,
            instructions=full_instruction,
            #TODO: pylance is not recognizing the type MCPStreamableHTTPTool as allowed FunctionTool
            tools=[account_mcp_server] #type: ignore
      )

      return agent