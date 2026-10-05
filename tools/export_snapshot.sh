#!/bin/bash
# Genera snapshot.md con el estado actual del proyecto (sin .env ni archivos pesados)
cd "$(dirname "$0")/.."
OUT="snapshot.md"
F=$(printf '\140\140\140')

{
  echo "# Snapshot del proyecto trading-scanner"
  echo "Generado: $(date '+%Y-%m-%d %H:%M:%S')"
  echo
  if [ -d .git ]; then
    echo "## Últimos commits"
    echo "$F"; git log --oneline -n 15 2>/dev/null; echo "$F"; echo
    echo "## Cambios sin commit"
    echo "$F"; git status --short; echo "$F"; echo
  fi
  echo "## Estructura"
  echo "$F"
  find . -type f \( -name "*.py" -o -name "*.sh" -o -name "*.md" -o -name "*.txt" \) \
    -not -path "./venv/*" -not -path "./.git/*" -not -path "*/__pycache__/*" \
    -not -name "snapshot.md" | sort
  echo "$F"; echo
  for f in README.md CHANGELOG.md CLAUDE.md requirements.txt; do
    if [ -f "$f" ]; then echo "## $f"; echo "$F"; cat "$f"; echo "$F"; echo; fi
  done
  echo "## Código"
  find . -type f \( -name "*.py" -o -name "*.sh" \) \
    -not -path "./venv/*" -not -path "./.git/*" -not -path "*/__pycache__/*" | sort | while read -r f; do
      echo "### $f"; echo "$F"; cat "$f"; echo "$F"; echo
  done
} > "$OUT"

echo "Listo: $OUT ($(wc -c < "$OUT") bytes)"
