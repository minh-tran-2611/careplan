from agent.workflows.multi_step_flow import multi_step_flow

class AgentController:
    def __init__(self,agent):self.agent=agent
    async def chat(self,request):return await multi_step_flow(self.agent,request)
