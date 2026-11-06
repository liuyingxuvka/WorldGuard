"""The declared exception routes stay together without another AST scanner."""
from flowguard.intent import allow, structure_rule
from tests.error_policy import NON_RAISING_HANDLERS, violations


@structure_rule('WG_ERROR_ROUTES', source='doc AGENTS.md "One route per function: when a step fails, the error reaches the caller or is reported with its text"')
def permitted_error_routes(graph):
    return violations(graph)


permitted_error_routes.allows(*(allow(key, value.reason) for key, value in NON_RAISING_HANDLERS.items()))
