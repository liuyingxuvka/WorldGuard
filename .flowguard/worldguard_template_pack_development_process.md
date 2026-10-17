# WorldGuard template development

`worldguard/template_packs.py` owns native registry/select/compose/slots/shape/routes/instance identity. The living `.flowguard/map.json` binds this owner, its model and ordinary tests. Historical OpenSpec archives record prior implementations, not current execution authority.

1. Inspect the current owner and affected fields. Update its canonical implementation, model and focused tests together when behavior changes.
2. Run only affected ordinary tests and the direct template-selection model. Model green does not imply actual domain execution.
3. Synchronize canonical source into the portable skill with `python scripts/sync_worldguard_portable_runtime.py sync`; audit it using `python scripts/check_runtime_identity.py`.
4. Refresh map dependencies/fingerprints and check current bindings. Commit and push the completed item.
5. After the final source freeze, run the ordinary full package tests once, build/install in a temporary consumer, compare exact identities, then publish the patch tag and Release at the same main commit.

A template or model change does not require another author framework, compiled control file, supervision receipt, nested pytest runner or release-proof loop. Installation and GitHub publication remain separately observed operations. World-model consistency never establishes factual truth outside its explicit evidence boundary.
