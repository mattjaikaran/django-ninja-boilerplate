#!/usr/bin/env bash
# Commit-msg hook — enforce tbaggery checks commitizen does not.
#
# commitizen validates the Conventional Commits format (type/scope prefix).
# This hook adds the tbaggery style rules that commitizen skips:
#   1. Subject line <= 50 characters (prefix included).
#   2. Subject line does not end with a period.
#   3. Body lines wrap at <= 72 characters.
#
# Wire this through pre-commit (see .pre-commit-config.yaml), NOT via a global
# core.hooksPath — a global hook path would bypass pre-commit entirely.

set -u

msg_file="${1:-}"
if [[ -z "${msg_file}" || ! -f "${msg_file}" ]]; then
    exit 0
fi

fail() { printf 'commit-msg: %s\n' "$1" >&2; }

status=0

subject="$(head -n 1 "${msg_file}")"

if (( ${#subject} > 50 )); then
    fail "subject is ${#subject} chars (limit 50): ${subject}"
    status=1
fi

if [[ "${subject}" =~ \.$ ]]; then
    fail "subject must not end with a period: ${subject}"
    status=1
fi

line_no=0
while IFS= read -r line; do
    line_no=$((line_no + 1))
    (( line_no == 1 )) && continue
    if (( ${#line} > 72 )); then
        fail "body line ${line_no} is ${#line} chars (wrap at 72)"
        status=1
    fi
done < "${msg_file}"

exit "${status}"
