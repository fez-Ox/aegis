# Shared launcher for NLQ shell scripts. Sourced, not executed.
# Pins this process to the repo Aegis venv (.venv, prompt=aegis).

if [[ -z "${REPO_ROOT:-}" ]]; then
  echo "REPO_ROOT must be set before sourcing _env.sh" >&2
  return 1 2>/dev/null || exit 1
fi

AEGIS_VENV="${REPO_ROOT}/.venv"
if [[ ! -f "${AEGIS_VENV}/bin/activate" ]]; then
  echo "Aegis env missing: ${AEGIS_VENV}" >&2
  return 1 2>/dev/null || exit 1
fi

# Drop any other active env and use Aegis for this process only.
# shellcheck source=/dev/null
source "${AEGIS_VENV}/bin/activate"

nlq_python() {
  python "$@"
}
