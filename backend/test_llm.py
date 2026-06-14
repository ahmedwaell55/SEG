import asyncio
from app.agents.nodes import full_analysis_agent
from app.models.entities import Meeting

async def run():
    state = {
        "raw_transcript": "Client: This is a test. We need a CRM. Sales: We can do that.",
        "cleaned_transcript": "Client: This is a test. We need a CRM.\nSales: We can do that."
    }
    result = await full_analysis_agent(state)
    print(result)

if __name__ == "__main__":
    asyncio.run(run())
