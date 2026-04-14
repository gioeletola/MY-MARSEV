"""
SOVEREIGN AI OS — Multi-agent orchestration operating system.

Built on the Anthropic Claude API with prompt caching and tool use.

Quick start:
    from sovereign.bootstrap import create_orchestrator
    import asyncio

    orch = create_orchestrator()
    result = asyncio.run(orch.handle_request("Your request here"))
    print(result.result)
"""
__version__ = "0.1.0"
__author__ = "MARSEV"
