# Multi-Agent Framework Brainstorming & Parking Lot

*Note: This document captures ideas for a standalone, public-facing product (e.g., the Data-TO-Value web app) that relies on a custom Multi-Agent System. This is distinct from local MCP server development.*

## The "Supervisor-Worker" Architecture

When building a standalone chatbot or web app, the "Supervisor-Worker" (or "Planner-Executor") pattern is an incredibly powerful paradigm. It separates high-level cognitive reasoning from tactical execution, reducing costs and preventing context-window overload.

### 1. The Supervisor (Heavy-Weight LLM)
*   **Recommended Models:** Gemini 1.5 Pro, GPT-4o, or Claude 3.5 Sonnet.
*   **Role:** The cognitive planner, user-facing conversationalist, and final evaluator. 
*   **Workflow:**
    1.  **Intent Classification:** Understands the user's high-level goal (e.g., asking a qualitative question about "laundry bylaws").
    2.  **Task Delegation:** Identifies the necessary steps (e.g., query RentSafeTO, find the webpage, extract text) and delegates them to specialized worker agents.
    3.  **Evaluation & Synthesis:** Evaluates the information returned by the workers, synthesizes the final response, and presents it to the user.

### 2. The Worker Agents (Small/Specialized Models)
*   **Recommended Models:** Gemini 1.5 Flash, Llama-3-8B, Claude 3 Haiku, or purely deterministic Python scripts.
*   **Role:** Tactical execution and targeted information retrieval.
*   **Types of Workers:**
    *   **CKAN Researcher:** A lightweight agent whose sole job is to query the `ckan-mcp-server`, find the relevant dataset (like `apartment-building-evaluation`), and extract the `url` metadata field.
    *   **Web Browser Agent:** An agent equipped with web scraping tools (like Firecrawl or a headless browser). It navigates the provided URL, handles pop-ups, and extracts raw text.
    *   **Document Parser Agent:** A specialized agent (e.g., using LlamaParse) that takes a PDF link, extracts the text, and searches for specific keywords (like "laundry") to return *only* the relevant paragraphs, saving massive context window space.

## Recommended Frameworks

To orchestrate this topology outside of standard chat environments, the following frameworks are ideal:
*   **LangGraph:** Excellent for defining complex, cyclical multi-agent workflows with explicit state management.
*   **CrewAI:** Provides a highly intuitive, role-based setup for defining teams of agents with specific tasks.

## Why Park This?
Building a robust Multi-Agent System requires significant infrastructure (state management, API routing, custom UI). For immediate local development and analysis, simply adding web-scraping tools to the existing `ckan-mcp-server` allows the current Antigravity chat window to act as the Supervisor without any additional framework overhead.
