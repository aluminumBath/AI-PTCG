*** Settings ***
Documentation     Agents can use a specific deck, a random deck, or their own pick.
Resource          resources/api.resource
Library           Collections
Suite Setup       Connect To API


*** Test Cases ***
Random And Agent Pick Resolve To Real Decks
    [Documentation]    'random' and 'auto' become concrete decks shown on the board.
    ${d}=    GET On Session    tcg    /api/decks
    ${ids}=    Set Variable    ${d.json()}[decks]
    ${body}=    Create Dictionary    mode=ai_vs_ai    deck_a=random    deck_b=auto
    ...    agent_a=aggro    agent_b=control    seed=${7}
    ${r}=    POST On Session    tcg    /api/game/new    json=${body}    expected_status=200
    ${j}=    Set Variable    ${r.json()}
    Should Not Be Empty    ${j}[deck_a]
    Should Not Be Empty    ${j}[deck_b]
    List Should Contain Value    ${ids}    ${j}[deck_a]
    List Should Contain Value    ${ids}    ${j}[deck_b]
    Should Be Equal    ${j}[state][players][0][name]    ${j}[deck_a]
    Should Be Equal    ${j}[state][players][1][name]    ${j}[deck_b]

Opponent Avoids Mirroring When Random
    ${body}=    Create Dictionary    mode=ai_vs_ai    deck_a=charizard_ex    deck_b=random
    ...    agent_a=heuristic    agent_b=heuristic    seed=${3}
    ${r}=    POST On Session    tcg    /api/game/new    json=${body}    expected_status=200
    Should Be Equal    ${r.json()}[deck_a]    charizard_ex
    Should Not Be Equal    ${r.json()}[deck_b]    charizard_ex

Specific Decks Are Preserved
    ${body}=    Create Dictionary    mode=ai_vs_ai    deck_a=charizard_ex    deck_b=miraidon_ex
    ${r}=    POST On Session    tcg    /api/game/new    json=${body}    expected_status=200
    Should Be Equal    ${r.json()}[deck_a]    charizard_ex
    Should Be Equal    ${r.json()}[deck_b]    miraidon_ex

Agent Pick Is Reproducible With A Seed
    ${body}=    Create Dictionary    mode=ai_vs_ai    deck_a=charizard_ex    deck_b=auto
    ...    agent_a=heuristic    agent_b=aggro    seed=${99}
    ${r1}=    POST On Session    tcg    /api/game/new    json=${body}    expected_status=200
    ${r2}=    POST On Session    tcg    /api/game/new    json=${body}    expected_status=200
    Should Be Equal    ${r1.json()}[deck_b]    ${r2.json()}[deck_b]
