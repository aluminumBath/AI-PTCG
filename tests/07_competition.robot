*** Settings ***
Documentation    PTCG AI Battle Challenge: info/readiness, the ISMCTS model, and the strategy report.
Library          RequestsLibrary
Library          Collections
Resource         resources/api.resource
Suite Setup      Connect To API


*** Test Cases ***
Competition Info Lists Both Categories And Readiness
    ${r}=    GET On Session    tcg    /api/competition/info
    Length Should Be    ${r.json()}[categories]    2
    Should Not Be Empty    ${r.json()}[readiness]
    ${urls}=    Evaluate    " ".join(c['url'] for c in $r.json()['categories'])
    Should Contain    ${urls}    pokemon-tcg-ai-battle

Imperfect-Information ISMCTS Model Is Registered
    ${r}=    GET On Session    tcg    /api/agents
    ${ids}=    Evaluate    [m['id'] for m in $r.json()['models']]
    Should Contain    ${ids}    ismcts

Strategy Report Is Generated From Live Results
    ${agents}=    Create List    heuristic    greedy
    ${decks}=    Create List    charizard_ex    gardevoir_ex
    ${body}=    Create Dictionary    agents=${agents}    decks=${decks}    games_per_pairing=${2}
    ${r}=    POST On Session    tcg    /api/competition/report    json=${body}    expected_status=200
    ${jid}=    Set Variable    ${r.json()}[job_id]
    Should Be Equal    ${r.json()}[status]    running
    Wait Until Keyword Succeeds    60x    2s    Report Job Done    ${jid}
    ${done}=    GET On Session    tcg    /api/competition/report/${jid}
    Should Contain    ${done.json()}[markdown]    Strategy Writeup
    Should Contain    ${done.json()}[markdown]    Leaderboard
    Should Be Equal    ${done.json()}[filename]    STRATEGY_REPORT.md


*** Keywords ***
Report Job Done
    [Arguments]    ${jid}
    ${r}=    GET On Session    tcg    /api/competition/report/${jid}
    Should Be Equal    ${r.json()}[status]    done
