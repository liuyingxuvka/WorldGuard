"""A continuation compares the two chapters' shared state and chronological order.

This finite boundary uses one shared fluent and one timed event in each chapter.
Resource transfers, tree aggregation and missing-time inputs retain direct tests.
"""
from flowguard.flow import Model
from flowguard.flow.adapter import fields

m = Model("chapter handoff", covers=["worldguard/mesh.py"],
          note="one shared fluent; complete numeric times; no resources or tree aggregation")
m.field("state_matches", (True, False), True)
m.field("time_forward", (True, False), True)
m.field("checked", (False, True), False)
m.field("state_failed", (False, True), False)
m.field("time_failed", (False, True), False)


@m.action(state_matches=(True, False), time_forward=(True, False))
def configure(s, state_matches, time_forward):
    s["state_matches"], s["time_forward"] = state_matches, time_forward
    s["checked"], s["state_failed"], s["time_failed"] = False, False, False


@m.action()
def check(s):
    s["checked"] = True
    s["state_failed"] = not s["state_matches"]
    s["time_failed"] = not s["time_forward"]


m.always("a different shared state is reported",
         lambda s: not s["checked"] or s["state_failed"] == (not s["state_matches"]))
m.always("a backwards chapter is reported",
         lambda s: not s["checked"] or s["time_failed"] == (not s["time_forward"]))
m.after("new chapter inputs invalidate the previous check", "configure",
        lambda before, after, state_matches, time_forward:
        not after["checked"] and not after["state_failed"] and not after["time_failed"])
m.after("the handoff check produces an observation", "check",
        lambda before, after: after["checked"])
m.reach("a compatible handoff is accepted",
        lambda s: s["checked"] and not s["state_failed"] and not s["time_failed"])
m.reach("both handoff contradictions remain visible",
        lambda s: s["checked"] and s["state_failed"] and s["time_failed"])
m.bind_adapter({"system": "tests.flow_migration.native_handoff:HandoffWorld",
                "classes": ["tests.flow_migration.native_handoff:HandoffWorld",
                            "worldguard.mesh:ModelMeshContract", "worldguard.mesh:ModelNode",
                            "worldguard.mesh:ModelEdge", "worldguard.mesh:MeshFinding",
                            "worldguard.contracts:GuardContract", "worldguard.contracts:Claim",
                            "worldguard.contracts:WorldModel", "worldguard.status:GuardStatus"]},
               state=lambda snapshot: fields(snapshot, names=("state_matches", "time_forward", "checked",
                                                             "state_failed", "time_failed")),
               operations={"configure": "configure", "check": "check"})
MODEL = m
