import httpx
import logging

class PentAGIClient:
    def __init__(self, base_url: str, api_token: str):
        # 如果数据库填的是 https://...:8443，则补齐全路径
        if "/api/v1/graphql" not in base_url:
            self.base_url = f"{base_url.rstrip('/')}/api/v1/graphql"
        else:
            self.base_url = base_url.rstrip('/')
            
        self.headers = {
            # 直接发送 Bearer + 原始 Token
            "Authorization": f"Bearer {api_token.strip()}",
            "Content-Type": "application/json"
        }

    async def _query(self, query: str, variables: dict = None):
        # verify=False 忽略自签名证书错误
        # follow_redirects=True 防止 301 重定向导致失败
        async with httpx.AsyncClient(timeout=60.0, verify=False, follow_redirects=True) as client:
            resp = await client.post(
                self.base_url, 
                json={"query": query, "variables": variables or {}}, 
                headers=self.headers
            )
            
            # 增加 422 状态码的详细报错信息，方便日后排查参数结构问题
            if resp.status_code == 422:
                raise Exception(f"请求参数不合法(422)，服务器返回: {resp.text}")
                
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                raise Exception(f"PentAGI API 报错: {data['errors']}")
            return data["data"]

    # ======= 修改点一：适配真实的创建任务参数 =======
    async def create_flow(self, provider: str, prompt: str):
        mutation = """
        mutation CreateFlow($provider: String!, $input: String!) {
          createFlow(modelProvider: $provider, input: $input) {
            id
            title
            status
          }
        }
        """
        variables = {
            "provider": provider,
            "input": prompt
        }
        result = await self._query(mutation, variables)
        return result["createFlow"]

    # ======= 修改点二：将查询参数名 id 改为 flowId =======
    async def get_flow_status(self, flow_id: str):
        query = """
        query GetFlow($flowId: ID!) {
          flow(flowId: $flowId) {
            id
            status
          }
        }
        """
        result = await self._query(query, {"flowId": flow_id})
        return result["flow"]
