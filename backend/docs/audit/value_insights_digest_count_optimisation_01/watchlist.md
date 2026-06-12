# VALUE-INSIGHTS-DIGEST-COUNT-OPTIMISATION-01

- [x] Post-deploy verification complete (`20260612T065647Z`)
- [x] Classification: VERIFIED_OPERATIONALLY
- [ ] Today/CC do not populate `unified:60:full` cache — value-insights still cold-fallbacks after Today/CC-only navigation (~31s digest stage)
- [ ] Consider extending cache peek to `today` / `command_center` surface keys in a future programme (not in scope now)
- [ ] Warm total endpoint still ~30s — `calculate_compliance_score` remains dominant (~13s local profiling estimate)
- [ ] Next candidate: value-insights compliance_score headline slice
