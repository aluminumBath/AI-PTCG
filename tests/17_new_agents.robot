*** Settings ***
Documentation     The four new agents (closer, momentum, mind-reader, coach) are
...               registered, documented, and usable to start a game.
Resource          resources/api.resource
Library           Collections
Suite Setup       Connect To API


*** Variables ***
@{NEW_AGENTS}     closer    momentum    mindreader    coach


*** Test Cases ***
New Agents Are Registered
    ${r}=    GET On Session    tcg    /api/agents    expected_status=200
    ${ids}=    Set Variable    ${r.json()}[agents]
    FOR    ${a}    IN    @{NEW_AGENTS}
        List Should Contain Value    ${ids}    ${a}
    END

New Agents Have Explainer Docs
    ${r}=    GET On Session    tcg    /api/models/docs    expected_status=200
    ${docs}=    Set Variable    ${r.json()}[models]
    ${doc_ids}=    Create List
    FOR    ${d}    IN    @{docs}
        Append To List    ${doc_ids}    ${d}[id]
    END
    FOR    ${a}    IN    @{NEW_AGENTS}
        List Should Contain Value    ${doc_ids}    ${a}
    END

Can Start A Game With The Closer
    ${body}=    Create Dictionary    deck_a=charizard_ex    deck_b=miraidon_ex    agent_a=closer    agent_b=heuristic
    ${r}=    POST On Session    tcg    /api/game/new    json=${body}    expected_status=200
    Dictionary Should Contain Key    ${r.json()}    game_id
