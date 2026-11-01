#!/bin/bash
# Install the ai-second-brain skill for your coding agents (symlinks, so `git pull` updates them all)
# and put a `brain` command on your PATH. Works with macOS's built-in bash 3.2.
#   bash tools/install-skill.sh              # claude + codex + kiro
#   bash tools/install-skill.sh codex kiro   # only some
set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL="$REPO/skills/ai-second-brain"
dest() {
  case "$1" in
    claude) echo "$HOME/.claude/skills" ;;   # Claude Code
    codex)  echo "$HOME/.agents/skills" ;;   # OpenAI Codex (user scope; other Agent Skills tools read it too)
    kiro)   echo "$HOME/.kiro/skills" ;;     # Kiro IDE + CLI
    *) echo "" ;;
  esac
}
[ $# -eq 0 ] && set -- claude codex kiro
for t in "$@"; do
  d="$(dest "$t")"; [ -z "$d" ] && { echo "unknown agent: $t (use claude, codex, kiro)"; continue; }
  mkdir -p "$d" && ln -sfn "$SKILL" "$d/ai-second-brain" && echo "✓ $t → $d/ai-second-brain"
done
mkdir -p "$HOME/.local/bin"
printf '#!/bin/bash\nexec python3 "%s/tools/brain.py" "$@"\n' "$REPO" > "$HOME/.local/bin/brain" && chmod +x "$HOME/.local/bin/brain"
echo "✓ brain command → ~/.local/bin/brain  (add ~/.local/bin to PATH if needed)"
echo "Devin: nothing to install — add this repo to Devin and it reads .agents/skills/ automatically."
