"""CodeRabbit AI Pipeline - DSPy-powered multi-agent code review system."""

__version__ = "0.1.0"
__author__ = "CodeRabbit Team"
__email__ = "team@coderabbit.ai"

from .agents import ContextEngineeringAgent, ReviewAgent, VerificationAgent
from .pipeline import CodeRabbitMultiAgentPipeline
from .models import *
from .config_models import *

__all__ = [
    "ContextEngineeringAgent",
    "ReviewAgent", 
    "VerificationAgent",
    "CodeRabbitMultiAgentPipeline",
    # All models and config models are exported via * imports
]