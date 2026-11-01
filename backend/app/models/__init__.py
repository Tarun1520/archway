"""
Data contracts: the shape of every piece of data Archway handles.

One file per group of related models, so each can be read on its own:

    common.py        shared helpers (ids, timestamps, the strict base class)
    lifecycle.py     run states and the rules for moving between them
    brief.py         ProjectBrief and its parts
    evidence.py      RepoEvidence, EvidenceItem
    eligibility.py   EligibilityResult
    receipt.py       DecisionReceipt
    option.py        ArchitectureOption and its parts
    roadmap.py       RoadmapTask
    prompt_pack.py   PromptPack and its parts
    usage.py         UsageEvent
    project.py       Project (and the request bodies to create or edit one)
    message.py       Message
    run.py           Run

These come from IMPLEMENTATION_GUIDE.md section 4.
Learn more: LEARNING_GUIDE.md topic 29.
"""
