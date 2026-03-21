from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Parse patterns like "1.", "1.2.", "1.2.3." etc. Tolerant to missing trailing dot.
_STEP_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\s*[\.\):\-]\s*(.+)", re.MULTILINE)
# Simpler fallback: lines starting with "- " or "* " or just numbered "N) ..."
_FALLBACK_RE = re.compile(r"^\s*(?:[-*]|\d+\s*[\).])\s*(.+)", re.MULTILINE)


@dataclass
class PlanStep:
    id: str  # "1", "1.2", "1.2.3"
    text: str
    children: list[PlanStep] = field(default_factory=list)

    @property
    def depth(self) -> int:
        return self.id.count(".")

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


class PlanState:
    """State machine for hierarchical plan decomposition.

    Phases:
        top_level   — waiting for initial 3-5 top-level steps
        decomposing — iteratively decomposing each step into sub-steps
        finalized   — all decomposition done, ready for execution
    """

    def __init__(
        self,
        max_depth: int = 2,
        min_steps: int = 3,
        max_steps: int = 5,
    ) -> None:
        self.max_depth = max_depth
        self.min_steps = min_steps
        self.max_steps = max_steps
        self.steps: list[PlanStep] = []
        self.phase: str = "top_level"
        self._current_decompose_target: str | None = None
        # Queue of step ids that still need decomposition
        self._decompose_queue: list[str] = []

    @property
    def finalized(self) -> bool:
        return self.phase == "finalized"

    def reset(self) -> None:
        """Reset state for replanning after failure."""
        self.steps = []
        self.phase = "top_level"
        self._current_decompose_target = None
        self._decompose_queue = []

    def submit_plan(self, plan_text: str) -> str:
        """Called by the show_plan tool. Returns guidance for the LLM."""
        if self.phase == "finalized":
            # Re-planning after failure: reset and accept new plan
            self.reset()
        if self.phase == "top_level":
            return self._accept_top_level(plan_text)
        elif self.phase == "decomposing":
            return self._accept_substeps(plan_text)
        return "Plan already finalized. Proceed with execution."

    # ------------------------------------------------------------------
    # Internal phase handlers
    # ------------------------------------------------------------------

    def _accept_top_level(self, text: str) -> str:
        steps = self._parse_steps(text, parent_prefix="")
        if not steps:
            return (
                f"Could not parse steps from your plan. "
                f"Please provide {self.min_steps}-{self.max_steps} numbered steps, e.g.:\n"
                f"1. First step\n2. Second step\n3. Third step"
            )

        if len(steps) < self.min_steps:
            return (
                f"Too few steps ({len(steps)}). "
                f"Provide at least {self.min_steps} steps."
            )
        if len(steps) > self.max_steps:
            # Silently trim to max
            steps = steps[: self.max_steps]

        self.steps = steps

        if self.max_depth <= 1:
            # Flat plan — finalize immediately
            self.phase = "finalized"
            flat = self.format_flat()
            return (
                f"Plan accepted ({len(self.steps)} steps). "
                f"Flat action list:\n{flat}\n"
                f"Execute the plan step by step."
            )

        # Start decomposition
        self._decompose_queue = [s.id for s in self.steps]
        return self._start_next_decomposition()

    def _accept_substeps(self, text: str) -> str:
        target_id = self._current_decompose_target
        if not target_id:
            return "No decomposition target. Plan may be finalized."

        parent = self._find_step(target_id)
        if not parent:
            return f"Step {target_id} not found."

        substeps = self._parse_steps(text, parent_prefix=target_id)
        if not substeps:
            return (
                f"Could not parse sub-steps for step {target_id}. "
                f"Provide numbered sub-steps, e.g.:\n"
                f"{target_id}.1. First sub-step\n{target_id}.2. Second sub-step"
            )

        parent.children = substeps

        # Check if these new substeps need further decomposition
        current_depth = parent.depth + 1  # children are one level deeper
        if current_depth < self.max_depth - 1:
            # Need to decompose these children too
            for s in substeps:
                self._decompose_queue.append(s.id)

        return self._start_next_decomposition()

    def _start_next_decomposition(self) -> str:
        """Pick the next step to decompose, or finalize."""
        while self._decompose_queue:
            next_id = self._decompose_queue.pop(0)
            step = self._find_step(next_id)
            if step and step.is_leaf:
                self._current_decompose_target = next_id
                self.phase = "decomposing"
                return (
                    f"Step {next_id} accepted. "
                    f"Now decompose step {next_id}: '{step.text}' "
                    f"into 2-4 concrete sub-steps by calling show_plan again."
                )

        # All done
        self.phase = "finalized"
        self._current_decompose_target = None
        flat = self.format_flat()
        return (
            f"All steps decomposed. Flat action list:\n{flat}\n"
            f"Execute the plan step by step."
        )

    # ------------------------------------------------------------------
    # Step lookup
    # ------------------------------------------------------------------

    def _find_step(self, step_id: str) -> PlanStep | None:
        """Find a step by its id in the tree."""
        return self._find_in(self.steps, step_id)

    def _find_in(self, steps: list[PlanStep], step_id: str) -> PlanStep | None:
        for s in steps:
            if s.id == step_id:
                return s
            found = self._find_in(s.children, step_id)
            if found:
                return found
        return None

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_steps(self, text: str, parent_prefix: str) -> list[PlanStep]:
        """Parse numbered steps from LLM text. Tolerant to various formats."""
        steps: list[PlanStep] = []

        # Try structured regex first
        for match in _STEP_RE.finditer(text):
            raw_id = match.group(1).rstrip(".")
            step_text = match.group(2).strip()
            if step_text:
                # Normalize the id: if parent is "2" and LLM writes "1. ..." -> "2.1"
                if parent_prefix:
                    # Check if LLM already used correct prefix
                    if raw_id.startswith(parent_prefix + "."):
                        step_id = raw_id
                    else:
                        # LLM wrote "1." instead of "2.1." — remap
                        step_id = f"{parent_prefix}.{raw_id}"
                else:
                    step_id = raw_id
                steps.append(PlanStep(id=step_id, text=step_text))

        if steps:
            return steps

        # Fallback: split by newlines and try to extract anything
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        for idx, line in enumerate(lines, 1):
            m = _FALLBACK_RE.match(line)
            content = m.group(1).strip() if m else line
            if content:
                if parent_prefix:
                    step_id = f"{parent_prefix}.{idx}"
                else:
                    step_id = str(idx)
                steps.append(PlanStep(id=step_id, text=content))

        return steps

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def flatten(self) -> list[PlanStep]:
        """Return flat list of leaf-level steps (actions to execute)."""
        result: list[PlanStep] = []
        self._collect_leaves(self.steps, result)
        return result

    def _collect_leaves(self, steps: list[PlanStep], out: list[PlanStep]) -> None:
        for s in steps:
            if s.is_leaf:
                out.append(s)
            else:
                self._collect_leaves(s.children, out)

    def format_tree(self) -> str:
        """Human-readable tree representation."""
        lines: list[str] = []
        self._format_tree_level(self.steps, lines, indent=0)
        return "\n".join(lines)

    def _format_tree_level(
        self, steps: list[PlanStep], lines: list[str], indent: int
    ) -> None:
        prefix = "  " * indent
        for s in steps:
            lines.append(f"{prefix}{s.id}. {s.text}")
            if s.children:
                self._format_tree_level(s.children, lines, indent + 1)

    def format_flat(self) -> str:
        """Numbered flat action list of leaf steps."""
        leaves = self.flatten()
        return "\n".join(f"{i+1}. [{s.id}] {s.text}" for i, s in enumerate(leaves))
