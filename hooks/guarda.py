#!/usr/bin/env python3
"""Guarda do spielberg (PreToolUse): Edit e Write só dentro deste repo.

O hemingway e a marca são só leitura. A mídia (~/Videos/syntaxis) é escrita pelo código do pipeline,
nunca pelo agente com Edit/Write. Escrita via Bash não passa por aqui: não use Bash para escrever fora.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ESCRITA = {"Edit", "Write", "NotebookEdit", "MultiEdit"}

d = json.load(sys.stdin)
if d.get("tool_name") in ESCRITA:
    entrada = d.get("tool_input") or {}
    alvo = entrada.get("file_path") or entrada.get("notebook_path") or ""
    real = os.path.realpath(os.path.join(d.get("cwd") or RAIZ, alvo))
    if real != RAIZ and not real.startswith(RAIZ + os.sep):
        print(f"bloqueado: {real} fica fora de {RAIZ}. hemingway e brand são só leitura.", file=sys.stderr)
        sys.exit(2)
