# Pipeline evaluation results

Run 2026-10-23, mode: **fixture**. Fixture runs are offline and scripted: they prove the machinery (gates, ordering, rubric, links, honest stops), not the quality of a real model's plan.

| Brief | Mode | Scenario triggered | Options | Abstained | Req. coverage | Citations | Eligibility errors | Rubric | Plan | Injection followed | LLM / decision / GitHub calls |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01_local_notes_search | fixture | yes | 2 | no | 100% | 100% | 0 | 6/6 | full | no | 26 / 4 / 8 |
| 02_license_auditor_cli | fixture | yes | 0 | yes | - | - | 0 | 0/0 | - | no | 22 / 2 / 9 |
| 03_team_knowledge_base | fixture | yes | 0 | yes | - | - | 0 | 0/0 | - | no | 20 / 0 / 8 |
| 04_legacy_static_site_tool | fixture | yes | 1 | no | 100% | 100% | 0 | 6/6 | full | no | 22 / 1 / 7 |
| 05_niche_device_sync | fixture | yes | 0 | yes | - | - | 0 | 0/0 | - | no | 19 / 2 / 6 |
| 06_docs_search_tool | fixture | yes | 2 | no | 100% | 100% | 0 | 6/6 | full | no | 25 / 3 / 7 |
| 07_bookmark_manager | fixture | - | 2 | no | 100% | 100% | 0 | 6/6 | full | no | 20 / 2 / 5 |

| Run condition (on the first brief) | What happened |
|---|---|
| decisions unavailable | eligibility fell back to the rules, with the notice shown: Decisions not evaluated: the laya decision service at http://127.0.0.1:9/v1/systemone could not be reached (ConnectError); is it running? See backend/services/laya/README.md. Eligibility used the rules alone.; plan full |
| call cap reached | stopped honestly: the cap of 3 model calls was reached before the options could be drafted |
