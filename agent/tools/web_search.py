import httpx

class WebSearchTool:
    """Optional search adapter, deliberately not used for clinical plan generation."""
    def __init__(self, endpoint: str = "", api_key: str = ""): self.endpoint,self.api_key=endpoint,api_key
    async def search(self,query:str):
        if not self.endpoint: return {"enabled":False,"results":[],"message":"Chưa cấu hình dịch vụ tìm kiếm. Chatbot chỉ dùng tài liệu nội bộ."}
        if not self.endpoint.startswith("https://"):raise ValueError("Search endpoint must use HTTPS")
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            response=await client.get(self.endpoint,params={"q":query[:500]},headers={"Authorization":"Bearer "+self.api_key} if self.api_key else {})
            response.raise_for_status();return response.json()
