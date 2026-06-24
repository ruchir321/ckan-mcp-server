"""Grounded civic-answer agent over Toronto Open Data.

A thin runtime that wraps the existing CKAN tools + document retrieval
(`document_scraper`) with a grounded Anthropic synthesis step: answer a civic
question ONLY from the City's own source documents, with citations, or abstain.
"""

from agent.grounded_agent import Citation, GroundedAnswer, answer_question

__all__ = ["answer_question", "GroundedAnswer", "Citation"]
