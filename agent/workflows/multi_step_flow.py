from agent.workflows.task_flow import task_flow

async def multi_step_flow(agent,request):
    """Conversation state comes from the client; no autonomous clinical actions."""
    return await task_flow(agent,request)
