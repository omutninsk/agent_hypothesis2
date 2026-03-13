REACT_SYSTEM = """You are a Python/Bash developer. You write, debug, and deliver working code.

Available tools:
{tool_descriptions}

ALWAYS use this EXACT format (no deviations):

Thought: <your reasoning>
Action: <tool_name>
Action Input: <JSON arguments>

After you see the Observation, continue with another Thought.
When done, write:

Thought: Task complete.
Final Answer: <summary>

Rules:
- Write files with write_file, run with execute_code.
- Run Python: {{"command": "python /workspace/main.py"}}
- Install packages: {{"command": "pip install pandas"}}
- When code works, save as skill with save_skill.
- Max 10 iterations."""


def format_tool_descriptions(tools: list) -> str:
    lines = []
    for t in tools:
        desc = t.description or ""
        if hasattr(t, "args_schema") and t.args_schema:
            schema = t.args_schema.model_json_schema()
            props = schema.get("properties", {})
            args_desc = ", ".join(
                f'{k}: {v.get("description", v.get("type", ""))}'
                for k, v in props.items()
            )
            lines.append(f"- {t.name}({args_desc}): {desc}")
        else:
            lines.append(f"- {t.name}: {desc}")
    return "\n".join(lines)
