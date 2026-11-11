async def task_flow(agent,request):
    """One grounded response: validate -> retrieve -> generate -> validate citations."""
    return await agent.respond(request)
