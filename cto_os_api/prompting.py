from __future__ import annotations

from .agents import get_agent
from .llm import LLMService
from .memory_engine import LocalMemoryEngine
from .models import GenerateRequest, GeneratedOutput, MemoryCreate
from .storage import JsonStore


class PromptService:
    def __init__(self, store: JsonStore, memory_engine: LocalMemoryEngine) -> None:
        self.store = store
        self.memory_engine = memory_engine
        self.llm = LLMService()

    def generate(self, project_id: str, request: GenerateRequest) -> GeneratedOutput:
        project = self.store.get_project(project_id)
        agent = get_agent(request.agent_id)
        if agent is None:
            raise KeyError(request.agent_id)

        query = request.memory_query or request.prompt
        memories = self.memory_engine.search(project_id, query=query, cross_project=request.cross_project)
        pinned = self.memory_engine.pinned_context(project_id)
        memory_ids = list(dict.fromkeys([m.id for m in pinned + memories]))

        prompt = request.prompt
        if request.template_id:
            template = self.store.get_prompt_template(request.template_id)
            body = template.template_body or template.template
            prompt = body.replace("{{prompt}}", request.prompt).replace("{{project}}", project.name)

        memory_block = "\n".join(f"- {m.title}: {m.content}" for m in pinned + memories)
        grounded_prompt = (
            f"Project: {project.name}\n\n"
            f"Working prompt:\n{prompt}\n\n"
            f"Source-of-truth and retrieved memory:\n{memory_block or '- No project memory matched yet.'}\n\n"
            "Return a practical internal CTO OS response with explicit assumptions and next actions."
        )
        llm_result = self.llm.generate(agent.system_prompt, grounded_prompt, {"project_id": project_id, "agent_id": agent.id})
        output_text = f"Agent: {agent.name.value}\nProject: {project.name}\n\n{llm_result.text}"

        generated = GeneratedOutput(
            project_id=project_id,
            agent_id=agent.id,
            prompt=prompt,
            output=output_text,
            memory_ids=memory_ids,
            metadata={
                "cross_project": request.cross_project,
                "llm": {key: value for key, value in llm_result.items() if key != "raw"},
                "raw_prompt": grounded_prompt,
            },
        )
        if request.save_output:
            self.store.save_output(generated)
        if request.save_as_memory:
            self.store.create_memory(
                project_id,
                MemoryCreate(
                    title=f"Generated output: {agent.name.value}",
                    content=output_text,
                    tags=["generated", agent.id],
                    source="generated_output",
                ),
            )
        return generated

    def _synthesize(self, system_prompt: str, prompt: str, has_memory: bool) -> str:
        grounding = "Grounded in pinned and retrieved project memory." if has_memory else "No matching memory was available, so assumptions are explicit."
        return (
            f"{grounding}\n"
            f"{system_prompt}\n\n"
            "1. Current read: summarize the core situation in one paragraph.\n"
            "2. Recommended move: state the highest-leverage next action.\n"
            "3. Tradeoffs: list the main constraint, risk, and expected upside.\n"
            "4. Execution: provide the next three concrete steps.\n\n"
            f"User request: {prompt}"
        )
