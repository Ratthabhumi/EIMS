# AI Inference & Agent Compute Platform

This zone houses our heavy mathematical workloads, Large Language Model (LLM) serving frameworks, vector indexing databases, and automated AI Workers.

## Target Deployment Infrastructure
* **Hardware Target**: Future Custom mATX Build (~60,000 THB Budget / Dedicated NVIDIA RTX AI GPU).
* **Network Mesh Integration**: Connected seamlessly to `homelab` (Ubuntu 24.04 Server) over encrypted Tailscale interconnect.

## Planned AI Engine Stack
1. **Ollama / vLLM Server**: High-throughput inference backend utilizing GPU acceleration to serve models (Llama 3, Mistral, Qwen, DeepSeek).
2. **Vector Database (Milvus / Qdrant / ChromaDB)**: Permanent memory storage for Retrieval-Augmented Generation (RAG) and document parsing.
3. **Open WebUI**: Local conversational user interface allowing multi-user secure chat over Tailscale from laptops and iPhones.
4. **Automated AI Agents (LangChain / LlamaIndex / Auto-DevOps)**: Custom automation workers with read-only observability access to diagnose infrastructure issues and write automation reports autonomously.
