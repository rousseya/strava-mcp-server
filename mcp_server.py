import inspect
from fastapi import FastAPI

class MCPServer:
    def __init__(self):
        self.app = FastAPI()
        self.tools = {}

    def tool(self, name):
        def decorator(func):
            self.tools[name] = func
            return func
        return decorator

    def create_app(self):
        @self.app.get("/tools")
        def list_tools():
            return {"tools": list(self.tools.keys())}

        @self.app.post("/tools/{tool_name}")
        async def run_tool(tool_name: str, params: dict = None):
            if tool_name not in self.tools:
                return {"error": "Tool not found"}
            
            tool_func = self.tools[tool_name]
            
            # Inspect the tool function's signature
            sig = inspect.signature(tool_func)
            tool_params = {}

            if params:
                for param_name, param in sig.parameters.items():
                    if param_name in params:
                        tool_params[param_name] = params[param_name]
            
            try:
                result = tool_func(**tool_params)
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}

        return self.app
