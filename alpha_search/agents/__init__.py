"""Alpha Search Agent Swarm — collaborative multi-agent system.

Five specialised agents collaborate through structured critique messages
and iterative improvement loops to discover, validate, and refine
quantitative trading strategies.

Quick start
-----------
>>> from alpha_search.agents import AgentSwarm, DataEngineerAgent, QuantEngineerAgent
>>> swarm = AgentSwarm()
>>> swarm.register("data_engineer", DataEngineerAgent())
>>> # ... register remaining agents ...
>>> result = swarm.run_collaboration(tickers, prices)
"""

from alpha_search.agents.swarm import AgentSwarm, CritiqueMessage
from alpha_search.agents.roles import (
    DataEngineerAgent,
    QuantEngineerAgent,
    RiskManagerAgent,
    ResearchAgent,
    OpportunityAgent,
)

__all__ = [
    "AgentSwarm",
    "CritiqueMessage",
    "DataEngineerAgent",
    "QuantEngineerAgent",
    "RiskManagerAgent",
    "ResearchAgent",
    "OpportunityAgent",
]

__version__ = "0.2.0"
