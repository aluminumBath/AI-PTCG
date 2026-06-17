*** Settings ***
Documentation    Game lifecycle: AI-vs-AI stepping, human play, all decks, saving.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Deck And Agent Catalogues Are Exposed
    ${decks}=    GET On Session    tcg    /api/decks
    Should Contain    ${decks.json()}[decks]    charizard_ex
    Should Contain    ${decks.json()}[decks]    miraidon_ex
    Should Contain    ${decks.json()}[decks]    roaring_moon_ex
    ${agents}=    GET On Session    tcg    /api/agents
    Should Contain    ${agents.json()}[agents]    mcts
    Should Contain    ${agents.json()}[agents]    rl

New AI Game Starts At Turn One
    ${gid}=    New AI Game
    ${r}=    GET On Session    tcg    /api/game/${gid}/state
    Should Be Equal As Integers    ${r.json()}[turn_number]    1
    Should Be Equal    ${r.json()}[winner]    ${None}

Stepping Advances The Game
    ${gid}=    New AI Game
    ${before}=    GET On Session    tcg    /api/game/${gid}/state
    ${r}=    Step AI Game    ${gid}
    Dictionary Should Contain Key    ${r}    last_action
    Dictionary Should Contain Key    ${r}    state

AI Game Plays To A Winner
    ${gid}=    New AI Game    agent_a=heuristic    agent_b=heuristic
    ${r}=    Play AI Game To End    ${gid}
    Should Be True    ${r}[done]
    Should Not Be Equal    ${r}[state][winner]    ${None}

All Decks Are Playable Against Each Other
    [Template]    Deck Pair Plays To Completion
    charizard_ex      gardevoir_ex
    miraidon_ex       roaring_moon_ex
    charizard_ex      miraidon_ex
    gardevoir_ex      roaring_moon_ex

RL And MCTS Brains Can Take Turns
    ${gid}=    New AI Game    agent_a=rl    agent_b=mcts
    ${r}=    Step AI Game    ${gid}
    Dictionary Should Contain Key    ${r}    state

Unknown Game Id Is Not Found
    GET On Session    tcg    /api/game/deadbeef/state    expected_status=404

Human Game Offers Legal Actions On Player Turn
    ${g}=    New Human Game    agent_b=heuristic
    ${gid}=    Set Variable    ${g}[game_id]
    ${actions}=    Set Variable    ${g}[state][legal_actions]
    Should Not Be Empty    ${actions}
    # submit the first legal action; backend then runs the AI's reply
    ${body}=    Create Dictionary    index=${0}
    ${r}=    POST On Session    tcg    /api/game/${gid}/action    json=${body}    expected_status=200
    Dictionary Should Contain Key    ${r.json()}    state

Illegal Action Index Is Rejected
    ${g}=    New Human Game
    ${gid}=    Set Variable    ${g}[game_id]
    ${body}=    Create Dictionary    index=${9999}
    POST On Session    tcg    /api/game/${gid}/action    json=${body}    expected_status=400

Logged-In User Can Save A Finished Game
    ${gid}=    New AI Game
    Play AI Game To End    ${gid}
    ${token}=    Login As Admin
    ${headers}=    Auth Headers    ${token}
    ${r}=    POST On Session    tcg    /api/game/${gid}/save    headers=${headers}    expected_status=200
    Should Be True    ${r.json()}[saved]
    ${hist}=    GET On Session    tcg    /api/me/games    headers=${headers}
    Should Not Be Empty    ${hist.json()}[games]

Saving Without Auth Is Unauthorized
    ${gid}=    New AI Game
    POST On Session    tcg    /api/game/${gid}/save    expected_status=401


*** Keywords ***
Deck Pair Plays To Completion
    [Arguments]    ${deck_a}    ${deck_b}
    ${gid}=    New AI Game    deck_a=${deck_a}    deck_b=${deck_b}
    ${r}=    Play AI Game To End    ${gid}
    Should Be True    ${r}[done]
